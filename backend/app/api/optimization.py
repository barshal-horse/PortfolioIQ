"""Portfolio optimization API endpoints."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.optimization import (
    BlackLittermanRequest,
    OptimizationRequest,
    OptimizationResponseData,
)
from app.services import optimization_engine

router = APIRouter(prefix="/portfolios", tags=["Portfolio Optimization"])


@router.post("/{portfolio_id}/optimize", response_model=SuccessResponse[OptimizationResponseData])
async def run_portfolio_optimization(
    portfolio_id: UUID,
    request: OptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run portfolio optimization using Mean-Variance, Max Sharpe, Min Volatility, or Risk Parity."""
    result = await optimization_engine.run_optimization(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        request=request,
    )
    return SuccessResponse(data=result.data)


@router.post("/{portfolio_id}/optimize/black-litterman", response_model=SuccessResponse[OptimizationResponseData])
async def run_black_litterman(
    portfolio_id: UUID,
    request: BlackLittermanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run Black-Litterman portfolio optimization incorporating subjective views."""
    result = await optimization_engine.run_black_litterman_optimization(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        request=request,
    )
    return SuccessResponse(data=result.data)


@router.get("/{portfolio_id}/optimize/history", response_model=SuccessResponse[List[OptimizationResponseData]])
async def get_optimization_runs_history(
    portfolio_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Max number of past runs to retrieve"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical optimization runs and results for a portfolio."""
    history = await optimization_engine.get_optimization_history(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        limit=limit,
    )
    return SuccessResponse(data=history)
