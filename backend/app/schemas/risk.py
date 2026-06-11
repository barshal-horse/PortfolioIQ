"""Pydantic schemas for risk analytics."""

from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SeriesData(BaseModel):
    """Time-series data for charting."""

    dates: list[str] = Field(..., description="ISO formatted dates (YYYY-MM-DD)")
    values: list[float] = Field(..., description="Corresponding numerical values")

    model_config = ConfigDict(from_attributes=True)


class RiskMetricsDetails(BaseModel):
    """Detailed calculated risk metrics."""

    annualized_return: float | None = None
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    beta: float | None = None
    alpha: float | None = None
    information_ratio: float | None = None
    tracking_error: float | None = None
    max_drawdown: float | None = None
    max_drawdown_start: str | None = None
    max_drawdown_end: str | None = None
    current_drawdown: float | None = None
    var_95: float | None = None
    var_99: float | None = None
    cvar_95: float | None = None
    cvar_99: float | None = None
    downside_deviation: float | None = None
    calmar_ratio: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None

    model_config = ConfigDict(from_attributes=True)


class RiskResponse(BaseModel):
    """Risk analysis response envelope."""

    portfolio_id: UUID
    calculation_date: datetime
    lookback_days: int
    risk_free_rate: float
    benchmark: str | None = None
    metrics: RiskMetricsDetails
    return_series: SeriesData | None = None
    drawdown_series: SeriesData | None = None

    model_config = ConfigDict(from_attributes=True)


class VaRResponse(BaseModel):
    """Detailed Value-at-Risk calculation response."""

    method: str = Field(..., description="Calculation method: historical, parametric, monte_carlo")
    confidence: float = Field(..., description="Confidence level, e.g. 0.95 or 0.99")
    horizon_days: int = Field(..., description="Horizon in trading days, e.g. 1, 5, 10, 21")
    var: float = Field(..., description="Value-at-Risk percentage (e.g. -0.0198 for -1.98%)")
    var_amount: float = Field(..., description="Value-at-Risk in portfolio currency value")
    cvar: float = Field(..., description="Conditional Value-at-Risk percentage")
    cvar_amount: float = Field(..., description="Conditional Value-at-Risk in currency value")
    portfolio_value: float = Field(..., description="Total portfolio value used for calculations")
    interpretation: str = Field(..., description="Plain-English explanation of the metrics")

    model_config = ConfigDict(from_attributes=True)


class HoldingRiskContribution(BaseModel):
    """Risk contribution details for a single holding."""

    ticker: str
    weight: float = Field(..., description="Current holding weight in the portfolio (0.0 to 1.0)")
    individual_volatility: float = Field(..., description="Annualized volatility of the holding")
    marginal_contribution: float = Field(..., description="Marginal contribution to portfolio volatility")
    percentage_contribution: float = Field(..., description="Percentage contribution of holding to total portfolio risk")
    beta_to_portfolio: float = Field(..., description="Beta of this holding relative to the portfolio returns")

    model_config = ConfigDict(from_attributes=True)


class RiskContributionsResponse(BaseModel):
    """Portfolio risk contributions decomposition response."""

    portfolio_volatility: float = Field(..., description="Annualized portfolio volatility")
    contributions: list[HoldingRiskContribution]

    model_config = ConfigDict(from_attributes=True)
