"""Pydantic schemas for portfolio optimization requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class OptimizationConstraints(BaseModel):
    """Portfolio optimization weight & exposure constraints."""

    min_weight: float = Field(0.0, ge=0.0, le=1.0, description="Minimum weight per asset")
    max_weight: float = Field(1.0, ge=0.0, le=1.0, description="Maximum weight per asset")
    sector_limits: Optional[Dict[str, float]] = Field(
        None, description="Maximum allocation limit per sector (e.g. {'Technology': 0.35})"
    )
    turnover_limit: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Maximum portfolio turnover allowed during rebalancing"
    )


class BlackLittermanView(BaseModel):
    """Investor subjective view for Black-Litterman model."""

    type: Literal["absolute", "relative"] = Field(
        ..., description="Type of view: 'absolute' (single asset) or 'relative' (asset pair)"
    )
    ticker: Optional[str] = Field(None, description="Target ticker for absolute view")
    long_ticker: Optional[str] = Field(None, description="Outperforming ticker for relative view")
    short_ticker: Optional[str] = Field(None, description="Underperforming ticker for relative view")
    expected_return: Optional[float] = Field(
        None, description="Expected annual return for absolute view (e.g. 0.15 for 15%)"
    )
    expected_outperformance: Optional[float] = Field(
        None, description="Expected outperformance spread for relative view (e.g. 0.05 for 5%)"
    )
    confidence: float = Field(
        0.5, ge=0.01, le=1.0, description="Confidence level in the view from 0.01 to 1.0"
    )


class OptimizationRequest(BaseModel):
    """Payload for standard portfolio optimization."""

    method: Literal[
        "mean_variance", "max_sharpe", "min_variance", "risk_parity", "black_litterman"
    ] = Field("max_sharpe", description="Optimization methodology")
    constraints: Optional[OptimizationConstraints] = Field(
        default_factory=OptimizationConstraints, description="Optimization constraints"
    )
    lookback_days: int = Field(252, ge=30, le=1260, description="Historical price days for covariance")
    risk_free_rate: float = Field(0.05, ge=-0.05, le=0.20, description="Annualized risk-free rate")


class BlackLittermanRequest(BaseModel):
    """Payload for Black-Litterman optimization with investor views."""

    views: List[BlackLittermanView] = Field(..., min_length=1, description="List of investor views")
    constraints: Optional[OptimizationConstraints] = Field(
        default_factory=OptimizationConstraints, description="Optimization constraints"
    )
    lookback_days: int = Field(252, ge=30, le=1260, description="Historical price days for prior")
    risk_free_rate: float = Field(0.05, ge=-0.05, le=0.20, description="Annualized risk-free rate")


class TradeRecommendation(BaseModel):
    """Rebalancing trade order recommendation."""

    ticker: str
    action: Literal["buy", "sell", "hold"]
    current_weight: float
    target_weight: float
    delta: float
    estimated_amount: float


class ExpectedMetrics(BaseModel):
    """Annualized portfolio expected performance metrics."""

    expected_return: float
    expected_volatility: float
    expected_sharpe: float


class FrontierPosition(BaseModel):
    """Single point on risk-return plot."""

    return_: float = Field(..., alias="return")
    volatility: float

    model_config = {"populate_by_name": True}


class EfficientFrontierData(BaseModel):
    """Coordinates for generating the Markowitz efficient frontier curve."""

    returns: List[float]
    volatilities: List[float]
    sharpe_ratios: List[float]
    current_position: Optional[FrontierPosition] = None
    optimal_position: Optional[FrontierPosition] = None


class OptimizationResponseData(BaseModel):
    """Optimization execution output data."""

    id: UUID
    method: str
    calculation_date: datetime
    current_allocation: Dict[str, float]
    optimal_allocation: Dict[str, float]
    expected_metrics: ExpectedMetrics
    current_metrics: Optional[ExpectedMetrics] = None
    trades: List[TradeRecommendation]
    efficient_frontier: Optional[EfficientFrontierData] = None
    views: Optional[List[Dict[str, Any]]] = None
    posterior_returns: Optional[Dict[str, float]] = None


class OptimizationResponse(BaseModel):
    """Standard API response wrapper for optimization."""

    status: str = "success"
    data: OptimizationResponseData
