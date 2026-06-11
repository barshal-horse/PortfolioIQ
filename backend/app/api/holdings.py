"""Holdings API endpoints — add, update, delete, bulk import."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.holding import (
    BulkHoldingsRequest,
    BulkHoldingsResponse,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
)
from app.services import portfolio_service

router = APIRouter(prefix="/portfolios/{portfolio_id}/holdings", tags=["Holdings"])


@router.post("", status_code=201, response_model=SuccessResponse[HoldingResponse])
async def add_holding(
    portfolio_id: UUID,
    data: HoldingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a single holding to a portfolio."""
    holding = await portfolio_service.add_holding(
        db, portfolio_id, current_user.id, data
    )
    return SuccessResponse(
        data=HoldingResponse(
            id=holding.id,
            ticker=holding.ticker,
            name=holding.instrument.name if holding.instrument else holding.ticker,
            sector=holding.instrument.sector if holding.instrument else None,
            quantity=float(holding.quantity),
            average_cost=float(holding.average_cost),
            current_price=float(holding.current_price),
            current_value=float(holding.current_value),
            cost_basis=float(holding.cost_basis),
            unrealized_pnl=float(holding.unrealized_pnl),
            weight=float(holding.weight),
            currency=holding.currency,
        )
    )


@router.put("/{holding_id}", response_model=SuccessResponse[HoldingResponse])
async def update_holding(
    portfolio_id: UUID,
    holding_id: UUID,
    data: HoldingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a holding's quantity or cost basis."""
    holding = await portfolio_service.update_holding(
        db, portfolio_id, holding_id, current_user.id, data
    )
    return SuccessResponse(
        data=HoldingResponse(
            id=holding.id,
            ticker=holding.ticker,
            name=holding.instrument.name if holding.instrument else holding.ticker,
            sector=holding.instrument.sector if holding.instrument else None,
            quantity=float(holding.quantity),
            average_cost=float(holding.average_cost),
            current_price=float(holding.current_price),
            current_value=float(holding.current_value),
            cost_basis=float(holding.cost_basis),
            unrealized_pnl=float(holding.unrealized_pnl),
            weight=float(holding.weight),
            currency=holding.currency,
        )
    )


@router.delete("/{holding_id}", status_code=204)
async def delete_holding(
    portfolio_id: UUID,
    holding_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a holding from a portfolio."""
    await portfolio_service.delete_holding(
        db, portfolio_id, holding_id, current_user.id
    )


@router.post("/bulk", status_code=201, response_model=SuccessResponse[BulkHoldingsResponse])
async def bulk_import(
    portfolio_id: UUID,
    data: BulkHoldingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk add/update holdings. Mode: 'merge' (upsert) or 'replace' (delete all + insert)."""
    result = await portfolio_service.bulk_import_holdings(
        db, portfolio_id, current_user.id, data.holdings, data.mode
    )

    holdings_responses = []
    for h in result["holdings"]:
        hr = HoldingResponse(
            id=h.id,
            ticker=h.ticker,
            name=h.instrument.name if h.instrument else h.ticker,
            sector=h.instrument.sector if h.instrument else None,
            quantity=float(h.quantity),
            average_cost=float(h.average_cost),
            current_price=float(h.current_price),
            current_value=float(h.current_value),
            cost_basis=float(h.cost_basis),
            unrealized_pnl=float(h.unrealized_pnl),
            weight=float(h.weight),
            currency=h.currency,
        )
        holdings_responses.append(hr)

    return SuccessResponse(
        data=BulkHoldingsResponse(
            added=result["added"],
            updated=result["updated"],
            deleted=result["deleted"],
            holdings=holdings_responses,
        )
    )
