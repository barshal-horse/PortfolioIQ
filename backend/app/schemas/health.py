"""Pydantic schemas for portfolio health scores and evaluations."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class HealthScoreSummary(BaseModel):
    """Overall portfolio health score summary."""

    score: int = Field(..., ge=0, le=100, description="Health score (0 - 100)")
    grade: str = Field(..., description="Overall health grade (excellent, good, fair, poor, critical)")
    explanation: str = Field(..., description="Human-readable explanation of the score")

    model_config = ConfigDict(from_attributes=True)


class SubscoreDiversificationDetails(BaseModel):
    """Details for diversification category subscore."""

    hhi: float = Field(..., description="Herfindahl-Hirschman Index value")
    sector_concentration: str = Field(..., description="Description of sector allocation concentration")
    num_holdings: int = Field(..., description="Number of assets in the portfolio")
    correlation_avg: float = Field(..., description="Average correlation coefficient among assets")
    explanation: str = Field(..., description="Heuristic explanation of diversification health")

    model_config = ConfigDict(from_attributes=True)


class SubscoreRiskDetails(BaseModel):
    """Details for risk category subscore."""

    vol_vs_benchmark: float = Field(..., description="Ratio of portfolio volatility to benchmark volatility")
    mdd_severity: str = Field(..., description="Drawdown severity description (low, moderate, high, extreme)")
    tail_risk: float = Field(..., description="95% Conditional Value-at-Risk daily percentage")
    explanation: str = Field(..., description="Heuristic explanation of risk health")

    model_config = ConfigDict(from_attributes=True)


class SubscorePerformanceDetails(BaseModel):
    """Details for performance category subscore."""

    returns_1m: float = Field(..., description="1-Month performance return percentage")
    returns_3m: float = Field(..., description="3-Month performance return percentage")
    returns_1y: float = Field(..., description="1-Year performance return percentage")
    consistency: float = Field(..., description="Fraction of positive daily returns in the period")
    explanation: str = Field(..., description="Heuristic explanation of performance health")

    model_config = ConfigDict(from_attributes=True)


class SubscoreEfficiencyDetails(BaseModel):
    """Details for efficiency category subscore."""

    sharpe_vs_benchmark: float = Field(..., description="Difference or ratio of portfolio Sharpe to benchmark Sharpe")
    information_ratio: float = Field(..., description="Information ratio value")
    return_per_risk: float = Field(..., description="Return divided by volatility")
    explanation: str = Field(..., description="Heuristic explanation of efficiency health")

    model_config = ConfigDict(from_attributes=True)


class SubscoreItem(BaseModel):
    """A single subscore category details."""

    score: int = Field(..., ge=0, le=100)
    grade: str
    weight: float = Field(..., description="Weighting of this subscore in overall score (e.g. 0.25)")
    details: dict = Field(..., description="Category-specific subscore detailed fields")

    model_config = ConfigDict(from_attributes=True)


class RecommendationItem(BaseModel):
    """An actionable portfolio optimization recommendation."""

    priority: str = Field(..., description="Priority level: high, medium, low")
    category: str = Field(..., description="Category: diversification, risk, performance, efficiency")
    action: str = Field(..., description="Proposed optimization action")
    rationale: str = Field(..., description="Scientific rationale for the action")

    model_config = ConfigDict(from_attributes=True)


class HealthSubscores(BaseModel):
    """Health subscores mapping by category."""

    diversification: SubscoreItem
    risk: SubscoreItem
    performance: SubscoreItem
    efficiency: SubscoreItem

    model_config = ConfigDict(from_attributes=True)


class HealthScoreResponse(BaseModel):
    """Portfolio health score full response."""

    portfolio_id: UUID
    calculation_date: datetime
    overall: HealthScoreSummary
    subscores: HealthSubscores
    recommendations: list[RecommendationItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RefreshResponse(BaseModel):
    """Recalculation start confirmation response."""

    message: str
    estimated_time_seconds: int
