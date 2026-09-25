"""Pydantic schemas for stress testing requests and responses."""

from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ── Scenario catalogue ──────────────────────────────────────────────

class ScenarioInfo(BaseModel):
    """Metadata for a single historical stress scenario."""

    id: str
    name: str
    start_date: str
    end_date: str
    sp500_return: float
    description: str


# ── Request ─────────────────────────────────────────────────────────

class StressTestRequest(BaseModel):
    """Payload for running stress test scenarios against a portfolio."""

    scenarios: List[
        Literal["gfc_2008", "covid_2020", "high_inflation_2022", "rate_shock_2022"]
    ] = Field(
        default_factory=lambda: [
            "gfc_2008",
            "covid_2020",
            "high_inflation_2022",
            "rate_shock_2022",
        ],
        description="Scenarios to simulate. Defaults to all four.",
    )


# ── Per-holding / per-sector impact items ───────────────────────────

class HoldingImpact(BaseModel):
    """Impact of a scenario on a single holding."""

    ticker: str
    return_: float = Field(..., alias="return")
    weight: float
    contribution: float

    model_config = {"populate_by_name": True}


class SectorImpact(BaseModel):
    """Impact of a scenario on a single sector."""

    sector: str
    return_: float = Field(..., alias="return")
    weight: float
    contribution: float

    model_config = {"populate_by_name": True}


# ── Single scenario result ──────────────────────────────────────────

class ScenarioResult(BaseModel):
    """Full result for one stress test scenario execution."""

    scenario: str
    description: str
    scenario_start: str
    scenario_end: str
    portfolio_return: float
    max_drawdown: float
    benchmark_return: Optional[float] = None
    recovery_days: Optional[int] = None
    holding_impacts: List[HoldingImpact]
    sector_impacts: List[SectorImpact]
    summary: str


# ── Top-level response ──────────────────────────────────────────────

class StressTestResponseData(BaseModel):
    """Container for all stress test scenario results."""

    portfolio_id: UUID
    calculation_date: datetime
    scenarios: List[ScenarioResult]


class StressTestResponse(BaseModel):
    """Standard API response wrapper for stress testing."""

    status: str = "success"
    data: StressTestResponseData
