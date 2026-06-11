"""Market data schemas — quote, history, portfolio valuation, returns, benchmarks."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    """Real-time quote details for a security."""

    ticker: str
    name: str | None = None
    price: float
    change: float
    change_percent: float
    volume: int | None = None
    market_cap: int | None = None
    pe_ratio: float | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str
    exchange: str | None = None
    last_updated: datetime


class HistoryPriceItem(BaseModel):
    """Single historical price data point."""

    date: str  # YYYY-MM-DD
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    adj_close: float
    volume: int | None = None


class HistoryResponse(BaseModel):
    """Historical prices response."""

    ticker: str
    period: str
    interval: str
    prices: list[HistoryPriceItem]


class ValuationSeriesItem(BaseModel):
    """Single data point in the portfolio valuation time series."""

    date: str  # YYYY-MM-DD
    value: float


class ValuationResponse(BaseModel):
    """Portfolio historical valuation response."""

    portfolio_id: UUID
    current_value: float
    period: str
    valuation_series: list[ValuationSeriesItem]
    total_return: float
    total_return_amount: float


class ReturnsSeriesItem(BaseModel):
    """Single return data point."""

    date: str  # YYYY-MM-DD
    daily_return: float


class ReturnsResponse(BaseModel):
    """Portfolio historical return series response."""

    portfolio_id: UUID
    period: str
    returns: list[ReturnsSeriesItem]
    cumulative_return: float
    annualized_return: float


class BenchmarkItem(BaseModel):
    """Benchmark index listing."""

    id: str  # SP500, NIFTY50, etc.
    name: str
    ticker: str
    currency: str
    current_value: float
    ytd_return: float | None = None
    one_year_return: float | None = Field(default=None, alias="1y_return")

    model_config = {
        "populate_by_name": True
    }
