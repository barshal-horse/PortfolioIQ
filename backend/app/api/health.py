"""Portfolio health evaluation API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.health import HealthScoreResponse, RefreshResponse
from app.services import health_service

router = APIRouter(prefix="/portfolios", tags=["Health Evaluation"])


@router.get("/{portfolio_id}/health", response_model=SuccessResponse[HealthScoreResponse])
async def get_portfolio_health_score(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the overall health score and subscore breakdown for a portfolio."""
    health_data = await health_service.calculate_portfolio_health(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
    )
    return SuccessResponse(data=health_data)


@router.post("/{portfolio_id}/health/refresh", status_code=status.HTTP_202_ACCEPTED, response_model=SuccessResponse[RefreshResponse])
async def refresh_portfolio_health_score(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force recalculation of the health score for a portfolio."""
    # Since calculations are fast (usually less than 1-2 seconds with cached histories),
    # we can run it synchronously inside the request flow, but return a 202 Accepted status 
    # to conform to the API Specification.
    await health_service.calculate_portfolio_health(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
    )
    refresh_data = RefreshResponse(
        message="Health score recalculation started",
        estimated_time_seconds=2,
    )
    return SuccessResponse(data=refresh_data)
