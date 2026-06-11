"""Portfolio service — CRUD, aggregate recalculation, holdings management."""

from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.schemas.holding import BulkHoldingItem, HoldingCreate, HoldingUpdate
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate, SectorAllocation


# ── Portfolio CRUD ────────────────────────────────────────────────────────


async def create_portfolio(
    db: AsyncSession, user_id: UUID, data: PortfolioCreate
) -> Portfolio:
    """Create a new portfolio for a user."""
    # Check name uniqueness per user
    existing = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == user_id, Portfolio.name == data.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Portfolio '{data.name}' already exists",
        )

    portfolio = Portfolio(
        user_id=user_id,
        name=data.name,
        description=data.description,
        base_currency=data.base_currency,
        benchmark=data.benchmark,
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def get_portfolios(
    db: AsyncSession,
    user_id: UUID,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Portfolio], int]:
    """List portfolios for a user with optional filtering and pagination."""
    query = select(Portfolio).where(Portfolio.user_id == user_id)
    count_query = select(func.count(Portfolio.id)).where(Portfolio.user_id == user_id)

    if status_filter:
        query = query.where(Portfolio.status == status_filter)
        count_query = count_query.where(Portfolio.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Portfolio.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    portfolios = list(result.scalars().all())

    # Attach holdings count
    for p in portfolios:
        count_result = await db.execute(
            select(func.count(Holding.id)).where(Holding.portfolio_id == p.id)
        )
        p._holdings_count = count_result.scalar() or 0

    return portfolios, total


async def get_portfolio_detail(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID
) -> Portfolio:
    """Get a portfolio with its holdings eagerly loaded."""
    result = await db.execute(
        select(Portfolio)
        .options(selectinload(Portfolio.holdings).selectinload(Holding.instrument))
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    return portfolio


async def update_portfolio(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID, data: PortfolioUpdate
) -> Portfolio:
    """Update portfolio metadata."""
    portfolio = await get_portfolio_detail(db, portfolio_id, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(portfolio, field, value)

    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def delete_portfolio(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID
) -> None:
    """Delete a portfolio and all associated data (cascade)."""
    portfolio = await get_portfolio_detail(db, portfolio_id, user_id)
    await db.delete(portfolio)
    await db.flush()


# ── Holdings Management ──────────────────────────────────────────────────


async def add_holding(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID, data: HoldingCreate
) -> Holding:
    """Add a single holding to a portfolio."""
    # Verify portfolio ownership
    portfolio = await get_portfolio_detail(db, portfolio_id, user_id)

    # Check for duplicate ticker
    existing = await db.execute(
        select(Holding).where(
            Holding.portfolio_id == portfolio_id,
            Holding.ticker == data.ticker.upper(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Holding for {data.ticker} already exists. Use PUT to update.",
        )

    # Find or create instrument
    instrument = await _get_or_create_instrument(db, data.ticker.upper())

    holding = Holding(
        portfolio_id=portfolio_id,
        instrument=instrument,
        ticker=data.ticker.upper(),
        quantity=data.quantity,
        average_cost=data.average_cost,
        current_price=data.average_cost,  # Default to cost until market data enriches
        currency=data.currency,
    )
    holding.recalculate()
    db.add(holding)
    await db.flush()

    # Recalculate portfolio aggregates
    await _recalculate_portfolio_aggregates(db, portfolio_id)

    # Query it back with eagerly loaded instrument to avoid lazy-loading issues
    result = await db.execute(
        select(Holding)
        .options(selectinload(Holding.instrument))
        .where(Holding.id == holding.id)
    )
    return result.scalar_one()


async def update_holding(
    db: AsyncSession,
    portfolio_id: UUID,
    holding_id: UUID,
    user_id: UUID,
    data: HoldingUpdate,
) -> Holding:
    """Update an existing holding's quantity or cost basis."""
    # Verify ownership
    await get_portfolio_detail(db, portfolio_id, user_id)

    result = await db.execute(
        select(Holding)
        .options(selectinload(Holding.instrument))
        .where(Holding.id == holding_id, Holding.portfolio_id == portfolio_id)
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found"
        )

    if data.quantity is not None:
        holding.quantity = data.quantity
    if data.average_cost is not None:
        holding.average_cost = data.average_cost

    holding.recalculate()
    await db.flush()
    await _recalculate_portfolio_aggregates(db, portfolio_id)

    # Query it back to get updated weight and ensure instrument is loaded
    res = await db.execute(
        select(Holding)
        .options(selectinload(Holding.instrument))
        .where(Holding.id == holding_id)
    )
    return res.scalar_one()


async def delete_holding(
    db: AsyncSession, portfolio_id: UUID, holding_id: UUID, user_id: UUID
) -> None:
    """Remove a holding from a portfolio."""
    await get_portfolio_detail(db, portfolio_id, user_id)

    result = await db.execute(
        select(Holding).where(
            Holding.id == holding_id, Holding.portfolio_id == portfolio_id
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found"
        )

    await db.delete(holding)
    await db.flush()
    await _recalculate_portfolio_aggregates(db, portfolio_id)


async def bulk_import_holdings(
    db: AsyncSession,
    portfolio_id: UUID,
    user_id: UUID,
    items: list[BulkHoldingItem],
    mode: str = "merge",
) -> dict:
    """Bulk import holdings. Mode: 'merge' (upsert) or 'replace' (delete all + insert)."""
    portfolio = await get_portfolio_detail(db, portfolio_id, user_id)

    added = 0
    updated = 0
    deleted = 0

    if mode == "replace":
        # Delete all existing holdings
        existing_holdings = await db.execute(
            select(Holding).where(Holding.portfolio_id == portfolio_id)
        )
        for h in existing_holdings.scalars().all():
            await db.delete(h)
            deleted += 1
        await db.flush()

    for item in items:
        ticker = item.ticker.upper()
        existing_result = await db.execute(
            select(Holding).where(
                Holding.portfolio_id == portfolio_id, Holding.ticker == ticker
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing and mode == "merge":
            existing.quantity = item.quantity
            existing.average_cost = item.average_cost
            existing.currency = item.currency
            existing.recalculate()
            updated += 1
        else:
            instrument = await _get_or_create_instrument(db, ticker)
            holding = Holding(
                portfolio_id=portfolio_id,
                instrument=instrument,
                ticker=ticker,
                quantity=item.quantity,
                average_cost=item.average_cost,
                current_price=item.average_cost,
                currency=item.currency,
            )
            holding.recalculate()
            db.add(holding)
            added += 1

    await db.flush()
    await _recalculate_portfolio_aggregates(db, portfolio_id)

    # Fetch updated holdings eagerly loading the instrument
    result = await db.execute(
        select(Holding)
        .options(selectinload(Holding.instrument))
        .where(Holding.portfolio_id == portfolio_id)
    )
    holdings = list(result.scalars().all())

    return {"added": added, "updated": updated, "deleted": deleted, "holdings": holdings}


def get_sector_allocation(holdings: list[Holding]) -> list[SectorAllocation]:
    """Compute sector allocation from a list of holdings."""
    sector_values: dict[str, float] = defaultdict(float)
    total_value = sum(float(h.current_value) for h in holdings)

    for h in holdings:
        sector = "Unknown"
        if h.instrument and h.instrument.sector:
            sector = h.instrument.sector
        sector_values[sector] += float(h.current_value)

    allocations = []
    for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
        weight = value / total_value if total_value > 0 else 0.0
        allocations.append(SectorAllocation(sector=sector, weight=weight, value=value))

    return allocations


# ── Internal Helpers ─────────────────────────────────────────────────────


async def _get_or_create_instrument(
    db: AsyncSession, ticker: str
) -> Instrument | None:
    """Find an instrument by ticker, or create a stub if not found."""
    result = await db.execute(
        select(Instrument).where(Instrument.ticker == ticker)
    )
    instrument = result.scalar_one_or_none()
    if instrument:
        return instrument

    # Create stub instrument — will be enriched by Market Data Service in Phase 3
    instrument = Instrument(
        ticker=ticker,
        name=ticker,  # Placeholder name
        instrument_type="equity",
    )
    db.add(instrument)
    await db.flush()
    return instrument


async def _recalculate_portfolio_aggregates(
    db: AsyncSession, portfolio_id: UUID
) -> None:
    """Recalculate total_value, total_cost, unrealized_pnl, weights for a portfolio."""
    result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    )
    holdings = list(result.scalars().all())

    total_value = sum(float(h.current_value) for h in holdings)
    total_cost = sum(float(h.cost_basis) for h in holdings)

    # Update weights
    for h in holdings:
        h.weight = float(h.current_value) / total_value if total_value > 0 else 0.0

    # Update portfolio aggregates
    portfolio_result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if portfolio:
        portfolio.total_value = total_value
        portfolio.total_cost = total_cost
        portfolio.unrealized_pnl = total_value - total_cost
        portfolio.pnl_percentage = (
            ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0.0
        )

    await db.flush()
