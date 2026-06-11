"""Risk analytics API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.risk import RiskResponse, VaRResponse, RiskContributionsResponse
from app.services import risk_engine

router = APIRouter(prefix="/portfolios", tags=["Risk Analytics"])


@router.get("/{portfolio_id}/risk", response_model=SuccessResponse[RiskResponse])
async def get_portfolio_risk(
    portfolio_id: UUID,
    lookback_days: int = Query(252, ge=30, le=1260, description="Number of trading days for lookback window"),
    benchmark: str | None = Query(None, description="Override portfolio default benchmark"),
    risk_free_rate: float | None = Query(None, ge=0.0, le=1.0, description="Override user default risk-free rate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate and return full risk metrics for the portfolio."""
    risk_data = await risk_engine.calculate_portfolio_risk(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        lookback_days=lookback_days,
        benchmark_override=benchmark,
        rf_override=risk_free_rate,
    )
    return SuccessResponse(data=risk_data)


@router.get("/{portfolio_id}/risk/var", response_model=SuccessResponse[VaRResponse])
async def get_portfolio_var(
    portfolio_id: UUID,
    method: str = Query("historical", pattern="^(historical|parametric|monte_carlo)$", description="VaR calculation method"),
    confidence: float = Query(0.95, ge=0.8, le=0.999, description="Confidence level (e.g. 0.95 or 0.99)"),
    horizon_days: int = Query(1, ge=1, le=100, description="Time horizon in trading days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate and return detailed Value-at-Risk (VaR) and Conditional VaR (CVaR)."""
    var_data = await risk_engine.calculate_var_details(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        method=method,
        confidence=confidence,
        horizon_days=horizon_days,
    )
    return SuccessResponse(data=var_data)


@router.get("/{portfolio_id}/risk/contributions", response_model=SuccessResponse[RiskContributionsResponse])
async def get_portfolio_risk_contributions(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate and return asset-level risk contributions to total portfolio risk."""
    contributions_data = await risk_engine.calculate_risk_contributions(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
    )
    return SuccessResponse(data=contributions_data)
