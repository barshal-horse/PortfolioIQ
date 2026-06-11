"""Benchmark comparison API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.benchmark import BenchmarkComparisonResponse
from app.services import benchmark_engine

router = APIRouter(prefix="/portfolios", tags=["Benchmarks"])


@router.get("/{portfolio_id}/benchmark", response_model=SuccessResponse[BenchmarkComparisonResponse])
async def get_portfolio_benchmark_comparison(
    portfolio_id: UUID,
    benchmark: str | None = Query(None, description="Benchmark identifier (e.g. SP500, NIFTY50) to compare against"),
    lookback_days: int = Query(252, ge=30, le=1260, description="Lookback window in trading days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate and return relative performance metrics against a benchmark index."""
    comparison_data = await benchmark_engine.calculate_benchmark_comparison(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        benchmark_override=benchmark,
        lookback_days=lookback_days,
    )
    return SuccessResponse(data=comparison_data)
