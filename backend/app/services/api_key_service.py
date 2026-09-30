"""API key settings service — per-user third-party keys (Gemini, etc.).

Mirrors the BrokerConnection pattern: base64 obfuscation, per-user rows,
upsert on save. The server-level env GEMINI_API_KEY (if any) always acts
as a fallback; a user-supplied key takes precedence for that user.
"""

import base64

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.api_key import ApiKeySetting
from app.utils.ids import to_uuid as _to_uuid


def _enc(plain: str) -> str:
    return base64.b64encode(plain.encode()).decode()


def _dec(blob: str) -> str:
    return base64.b64decode(blob.encode()).decode()


PROVIDER_GEMINI = "gemini"


async def save_api_key(
    db: AsyncSession, user_id, provider: str, key: str
) -> dict:
    """Upsert a provider API key for the user. Returns minimal status info."""
    user_id = _to_uuid(user_id)
    provider = provider.strip().lower()
    key = key.strip()
    if not key:
        raise ValueError("API key must not be empty")

    result = await db.execute(
        select(ApiKeySetting).where(
            ApiKeySetting.user_id == user_id,
            ApiKeySetting.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.key_enc = _enc(key)
    else:
        db.add(ApiKeySetting(user_id=user_id, provider=provider, key_enc=_enc(key)))
    await db.flush()
    return {"provider": provider, "saved": True}


async def delete_api_key(db: AsyncSession, user_id, provider: str) -> dict:
    """Remove the user's stored key for a provider."""
    user_id = _to_uuid(user_id)
    provider = provider.strip().lower()
    await db.execute(
        delete(ApiKeySetting).where(
            ApiKeySetting.user_id == user_id,
            ApiKeySetting.provider == provider,
        )
    )
    await db.flush()
    return {"provider": provider, "deleted": True}


async def get_user_api_key(db: AsyncSession, user_id, provider: str) -> str | None:
    """Return the user's stored key for a provider (decoded), or None."""
    user_id = _to_uuid(user_id)
    result = await db.execute(
        select(ApiKeySetting).where(
            ApiKeySetting.user_id == user_id,
            ApiKeySetting.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    try:
        return _dec(row.key_enc)
    except Exception:
        return None


def get_server_gemini_key() -> str | None:
    """Server-level env key (backend/.env), used as fallback."""
    return get_settings().gemini_api_key or None


async def validate_gemini_key(key: str) -> tuple[bool, str | None]:
    """Check a Gemini key with a minimal live call.

    Returns (ok, error_message). Prevents saving keys Google rejects
    (typo, revoked, wrong service) — the UI surfaces the error.
    """
    import asyncio

    def _check() -> tuple[bool, str | None]:
        from google import genai
        try:
            client = genai.Client(api_key=key.strip())
            client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Reply with exactly: OK",
            )
            return True, None
        except Exception as e:
            msg = str(e)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                return False, "Google rejected this key (API_KEY_INVALID). Double-check you copied the full key from Google AI Studio."
            if "quota" in msg.lower() or "429" in msg:
                # Rate-limited but the key itself authenticated.
                return True, None
            return False, f"Gemini validation failed: {msg[:200]}"

    return await asyncio.to_thread(_check)


async def resolve_gemini_key(db: AsyncSession, user_id) -> str | None:
    """User-stored Gemini key first, then the server env key."""
    return (await get_user_api_key(db, user_id, PROVIDER_GEMINI)) or get_server_gemini_key()
