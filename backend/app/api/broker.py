"""Broker sync API endpoints — Alpaca connect, positions, sync to portfolio."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.schemas.common import SuccessResponse
from app.services import portfolio_service
from app.services.broker_service import (
    alpaca_service,
    connect_alpaca,
    disconnect_broker,
    get_connection_status,
    get_stored_positions,
)
from sqlalchemy import and_, select

router = APIRouter(prefix="/broker", tags=["Broker Sync"])


# ── Schemas ──────────────────────────────────────────────────────────────


class ConnectRequest(BaseModel):
    api_key: str
    api_secret: str


class ConnectionStatus(BaseModel):
    broker: str
    account_number: Optional[str]
    status: Optional[str]
    last_sync_at: Optional[str]


class BrokerPosition(BaseModel):
    ticker: str
    quantity: float
    average_cost: float
    current_price: float
    currency: str


class SyncResult(BaseModel):
    synced: int
    added: int
    updated: int
    tickers: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post("/connect", response_model=SuccessResponse[dict])
async def connect_broker(
    request: ConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify and store Alpaca API credentials for the current user."""
    result = await connect_alpaca(db, current_user.id, request.api_key.strip(), request.api_secret.strip())
    return SuccessResponse(data=result)


@router.get("/status", response_model=SuccessResponse[Optional[ConnectionStatus]])
async def broker_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's broker connection status (null if not connected)."""
    status = await get_connection_status(db, current_user.id)
    return SuccessResponse(data=status)


@router.post("/disconnect", response_model=SuccessResponse[dict])
async def disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the stored broker connection."""
    result = await disconnect_broker(db, current_user.id)
    return SuccessResponse(data=result)


@router.get("/positions", response_model=SuccessResponse[list[BrokerPosition]])
async def broker_positions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch live positions from the connected broker."""
    positions = await get_stored_positions(db, current_user.id)
    return SuccessResponse(data=[BrokerPosition(**p) for p in positions])


@router.get("/account", response_model=SuccessResponse[dict])
async def broker_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch broker account summary."""
    from app.services.broker_service import get_connection, _dec

    conn = await get_connection(db, current_user.id)
    if not conn:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="No broker connected")
    account = await alpaca_service.verify_credentials(_dec(conn.api_key_enc), _dec(conn.api_secret_enc))
    return SuccessResponse(data=account)


@router.post("/sync/{portfolio_id}", response_model=SuccessResponse[SyncResult])
async def sync_positions_to_portfolio(
    portfolio_id: UUID,
    mode: str = Query("merge", pattern=r"^(merge|replace)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pull broker positions into a portfolio (merge updates/adds, replace resets first)."""
    # Verify portfolio ownership
    await portfolio_service.get_portfolio_detail(db, portfolio_id, current_user.id)

    positions = await get_stored_positions(db, current_user.id)
    if not positions:
        return SuccessResponse(data=SyncResult(synced=0, added=0, updated=0, tickers=[]))

    existing = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    )
    existing_map = {h.ticker.upper(): h for h in existing.scalars().all()}

    if mode == "replace" and existing_map:
        for h in existing_map.values():
            await db.delete(h)
        await db.flush()
        existing_map = {}

    added = updated = 0
    tickers = []
    for p in positions:
        ticker = p["ticker"].upper()
        tickers.append(ticker)
        current = existing_map.get(ticker)
        if current:
            current.quantity = p["quantity"]
            current.average_cost = p["average_cost"]
            current.current_price = p["current_price"]
            current.recalculate()
            updated += 1
        else:
            holding = Holding(
                portfolio_id=portfolio_id,
                ticker=ticker,
                quantity=p["quantity"],
                average_cost=p["average_cost"],
                current_price=p["current_price"],
                currency=p.get("currency", "USD"),
            )
            holding.recalculate()
            db.add(holding)
            added += 1

    # Recompute portfolio aggregates (weights, totals)
    await portfolio_service._recalculate_portfolio_aggregates(db, portfolio_id)

    from datetime import datetime, timezone
    from app.services.broker_service import get_connection

    conn = await get_connection(db, current_user.id)
    if conn:
        conn.last_sync_at = datetime.now(timezone.utc)

    await db.flush()
    return SuccessResponse(
        data=SyncResult(synced=len(positions), added=added, updated=updated, tickers=tickers)
    )
