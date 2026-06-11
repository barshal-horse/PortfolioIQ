"""Benchmarks API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.market_data import BenchmarkItem
from app.services import market_data_service

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])


@router.get("", response_model=SuccessResponse[list[BenchmarkItem]])
async def get_benchmarks_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available benchmarks with current values and returns."""
    benchmarks = await market_data_service.get_benchmarks(db)
    return SuccessResponse(data=benchmarks)
