"""Pydantic schemas for benchmark comparison analytics."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.risk import SeriesData


class ComparisonSeries(BaseModel):
    """Growth index series comparing portfolio against benchmark."""

    dates: list[str] = Field(..., description="ISO formatted dates (YYYY-MM-DD)")
    portfolio: list[float] = Field(..., description="Portfolio growth series values (starts at 1.0)")
    benchmark: list[float] = Field(..., description="Benchmark growth series values (starts at 1.0)")

    model_config = ConfigDict(from_attributes=True)


class PeriodReturnItem(BaseModel):
    """Portfolio and benchmark returns comparison for a single period."""

    portfolio: float = Field(..., description="Portfolio return percentage for the period")
    benchmark: float = Field(..., description="Benchmark return percentage for the period")

    model_config = ConfigDict(from_attributes=True)


class PeriodReturns(BaseModel):
    """Relative return metrics across different time windows."""

    one_month: PeriodReturnItem = Field(..., alias="1m")
    three_month: PeriodReturnItem = Field(..., alias="3m")
    six_month: PeriodReturnItem = Field(..., alias="6m")
    one_year: PeriodReturnItem = Field(..., alias="1y")
    ytd: PeriodReturnItem = Field(..., description="Year-To-Date returns comparison")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BenchmarkMetrics(BaseModel):
    """Historical relative statistics against the index."""

    active_return: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    alpha: float | None = None
    beta: float | None = None
    upside_capture: float | None = None
    downside_capture: float | None = None

    model_config = ConfigDict(from_attributes=True)


class BenchmarkComparisonResponse(BaseModel):
    """Full benchmark comparison results schema."""

    portfolio_id: UUID
    benchmark: str
    calculation_date: datetime
    lookback_days: int
    metrics: BenchmarkMetrics
    period_returns: PeriodReturns
    cumulative_comparison: ComparisonSeries
    rolling_alpha: SeriesData
    rolling_beta: SeriesData
    rolling_correlation: SeriesData

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
