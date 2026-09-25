"""Stress Testing API endpoints — historical crisis scenario simulation."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.stress_test import (
    ScenarioInfo,
    StressTestRequest,
    StressTestResponseData,
)
from app.services import stress_testing_engine

router = APIRouter(prefix="/portfolios", tags=["Stress Testing"])


@router.post(
    "/{portfolio_id}/stress-test",
    response_model=SuccessResponse[StressTestResponseData],
)
async def run_stress_test(
    portfolio_id: UUID,
    request: StressTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run one or more historical stress test scenarios against a portfolio.

    Simulates the selected crisis scenarios (2008 GFC, COVID-19 crash, 2022
    inflation regime, or 2022-23 rate shock) using actual historical prices
    for every holding in the portfolio.
    """
    result = await stress_testing_engine.run_stress_test(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        request=request,
    )
    return SuccessResponse(data=result.data)


@router.get(
    "/stress-test/scenarios",
    response_model=SuccessResponse[List[ScenarioInfo]],
)
async def list_stress_test_scenarios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available built-in stress test scenarios with metadata."""
    scenarios = stress_testing_engine.get_available_scenarios()
    return SuccessResponse(data=scenarios)


@router.get(
    "/{portfolio_id}/stress-test/history",
    response_model=SuccessResponse[List[dict]],
)
async def get_stress_test_history(
    portfolio_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Max number of past runs to retrieve"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical stress test runs for a portfolio."""
    history = await stress_testing_engine.get_stress_test_history(
        db,
        portfolio_id=str(portfolio_id),
        user_id=str(current_user.id),
        limit=limit,
    )
    return SuccessResponse(data=history)