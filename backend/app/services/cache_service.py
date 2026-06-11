"""Cache service — 2-tier caching (in-memory and database-backed) with TTL."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import CacheEntry

# Tier 1: In-Memory Cache (Global dictionary storage)
_IN_MEMORY_CACHE: dict[str, tuple[dict, datetime]] = {}


def get_in_memory(key: str) -> dict | None:
    """Get item from in-memory cache if not expired."""
    if key in _IN_MEMORY_CACHE:
        value, expires_at = _IN_MEMORY_CACHE[key]
        if expires_at > datetime.now(timezone.utc):
            return value
        else:
            # Clean up expired entry
            del _IN_MEMORY_CACHE[key]
    return None


def set_in_memory(key: str, value: dict, expires_at: datetime) -> None:
    """Store item in in-memory cache."""
    _IN_MEMORY_CACHE[key] = (value, expires_at)


def delete_in_memory(key: str) -> None:
    """Delete item from in-memory cache."""
    if key in _IN_MEMORY_CACHE:
        del _IN_MEMORY_CACHE[key]


def clear_in_memory_category(category: str) -> None:
    """Clear all in-memory entries for a category (currently we do full clear of matching prefixes or full clear)."""
    # Simple clear of memory cache
    _IN_MEMORY_CACHE.clear()


# Tier 2: Database-Backed Cache APIs


async def get_cached_item(db: AsyncSession, key: str) -> dict | None:
    """Get a cached item, checking in-memory first, then database."""
    # 1. Check in-memory (Tier 1)
    in_mem_val = get_in_memory(key)
    if in_mem_val is not None:
        return in_mem_val

    # 2. Check Database (Tier 2)
    result = await db.execute(select(CacheEntry).where(CacheEntry.key == key))
    entry = result.scalar_one_or_none()

    if entry:
        now = datetime.now(timezone.utc)
        # Ensure expires_at is timezone-aware
        expires_at = entry.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at > now:
            # Backfill to in-memory cache and return
            set_in_memory(key, entry.value, expires_at)
            return entry.value
        else:
            # Delete expired entry from database
            await db.delete(entry)
            await db.flush()

    return None


async def set_cached_item(
    db: AsyncSession, key: str, value: dict, category: str, ttl_seconds: int
) -> None:
    """Store an item in both in-memory and database-backed caches."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    # 1. Update in-memory
    set_in_memory(key, value, expires_at)

    # 2. Update database
    result = await db.execute(select(CacheEntry).where(CacheEntry.key == key))
    entry = result.scalar_one_or_none()

    if entry:
        entry.value = value
        entry.category = category
        entry.expires_at = expires_at
    else:
        entry = CacheEntry(
            key=key,
            value=value,
            category=category,
            expires_at=expires_at,
        )
        db.add(entry)

    await db.flush()


async def delete_cached_item(db: AsyncSession, key: str) -> None:
    """Remove a specific key from all caches."""
    delete_in_memory(key)
    await db.execute(delete(CacheEntry).where(CacheEntry.key == key))
    await db.flush()


async def invalidate_category(db: AsyncSession, category: str) -> None:
    """Invalidate all cache entries belonging to a given category."""
    clear_in_memory_category(category)
    await db.execute(delete(CacheEntry).where(CacheEntry.category == category))
    await db.flush()
