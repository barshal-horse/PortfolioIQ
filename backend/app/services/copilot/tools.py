"""Copilot Tools — wrapping existing service layer methods for LangGraph agents."""

import uuid
from typing import Any, Dict, List, Optional
from datetime import date
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.portfolio import Portfolio
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.user import User
from app.services import market_data_service
from app.services import risk_engine
from app.services import benchmark_engine
from app.services import health_service
from app.services import optimization_engine
from app.services import stress_testing_engine  # noqa: F401
from app.schemas.risk import RiskResponse
from app.schemas.benchmark import BenchmarkComparisonResponse
from app.schemas.health import HealthScoreResponse
from app.schemas.optimization import OptimizationResponse
from app.schemas.stress_test import StressTestResponse


# Helper functions
async def _get_portfolio(db: AsyncSession, portfolio_id: str, user_id: str) -> Portfolio:
    """Fetch portfolio with holdings."""
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.id == uuid.UUID(portfolio_id))
        .where(Portfolio.user_id == uuid.UUID(user_id))
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise ValueError("Portfolio not found")
    return portfolio


def _get_db_session() -> AsyncSession:
    """Get a database session. In production, this would be injected."""
    return next(get_db())


# ── Portfolio Context Tools ────────────────────────────────────────────────

@tool
async def get_portfolio_summary(portfolio_id: str, user_id: str) -> dict:
    """Get basic portfolio information including holdings and current values."""
    async for db in get_db():
        portfolio = await _get_portfolio(db, portfolio_id, user_id)
        
        # Get holdings with current values
        holdings_result = await db.execute(
            select(Holding, Instrument)
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .where(Holding.portfolio_id == uuid.UUID(portfolio_id))
        )
        holdings = holdings_result.all()
        
        return {
            "portfolio_id": str(portfolio.id),
            "name": portfolio.name,
            "total_value": float(portfolio.total_value or 0),
            "total_cost": float(portfolio.total_cost or 0),
            "unrealized_pnl": float(portfolio.unrealized_pnl or 0),
            "pnl_percentage": float(portfolio.pnl_percentage or 0),
            "benchmark": portfolio.benchmark,
            "base_currency": portfolio.base_currency,
            "holdings": [
                {
                    "ticker": h.ticker,
                    "name": i.name if i else h.ticker,
                    "sector": i.sector if i else None,
                    "quantity": float(h.quantity),
                    "average_cost": float(h.average_cost),
                    "current_price": float(h.current_price),
                    "current_value": float(h.current_value),
                    "weight": float(h.weight),
                    "unrealized_pnl": float(h.unrealized_pnl),
                }
                for h, i in holdings
            ],
        }


@tool
async def get_sector_allocation(portfolio_id: str, user_id: str) -> dict:
    """Get sector allocation breakdown for a portfolio."""
    async for db in get_db():
        portfolio = await _get_portfolio(db, portfolio_id, user_id)
        
        holdings_result = await db.execute(
            select(Holding, Instrument)
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .where(Holding.portfolio_id == uuid.UUID(portfolio_id))
        )
        holdings = holdings_result.all()
        
        sector_map = {}
        for h, i in holdings:
            sector = i.sector if i and i.sector else "General"
            value = float(h.current_value or 0)
            sector_map[sector] = sector_map.get(sector, 0) + value
        
        total = sum(sector_map.values())
        return {
            "sectors": {k: round(v / total * 100, 2) if total > 0 else 0 for k, v in sector_map.items()},
            "total_value": total,
        }


# ── Risk Analytics Tools ───────────────────────────────────────────────────

@tool
async def get_risk_metrics(
    portfolio_id: str,
    user_id: str,
    lookback_days: int = 252,
    benchmark: str = "SP500",
    risk_free_rate: float = 0.05,
) -> dict:
    """Calculate comprehensive risk metrics for a portfolio."""
    async for db in get_db():
        result = await risk_engine.calculate_portfolio_risk(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            lookback_days=lookback_days,
            benchmark_override=benchmark,
            rf_override=risk_free_rate,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_var_analysis(
    portfolio_id: str,
    user_id: str,
    method: str = "historical",
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> dict:
    """Calculate Value at Risk and Conditional VaR details."""
    async for db in get_db():
        result = await risk_engine.calculate_var_details(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            method=method,
            confidence=confidence,
            horizon_days=horizon_days,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_risk_contributions(portfolio_id: str, user_id: str) -> dict:
    """Get per-holding risk contributions (Euler decomposition)."""
    async for db in get_db():
        result = await risk_engine.calculate_risk_contributions(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_return_series(
    portfolio_id: str,
    user_id: str,
    period: str = "1y",
) -> dict:
    """Get historical return series for a portfolio."""
    async for db in get_db():
        result = await market_data_service.get_portfolio_returns_series(
            db, portfolio_id, user_id, period
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


# ── Benchmark Comparison Tools ──────────────────────────────────────────────

@tool
async def get_benchmark_comparison(
    portfolio_id: str,
    user_id: str,
    benchmark: str = "SP500",
    lookback_days: int = 252,
) -> dict:
    """Compare portfolio performance against a benchmark."""
    async for db in get_db():
        result = await benchmark_engine.calculate_benchmark_comparison(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            benchmark_override=benchmark,
            lookback_days=lookback_days,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_capture_ratios(portfolio_id: str, user_id: str, benchmark: str = "SP500") -> dict:
    """Get upside/downside capture ratios vs benchmark."""
    async for db in get_db():
        result = await benchmark_engine.calculate_benchmark_comparison(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            benchmark_override=benchmark,
            lookback_days=252,
        )
        return {
            "upside_capture": getattr(result.metrics, 'upside_capture', None),
            "downside_capture": getattr(result.metrics, 'downside_capture', None),
        }


@tool
async def get_benchmark_list() -> list[str]:
    """Get list of available benchmarks."""
    return ["SP500", "NASDAQ100", "NIFTY50", "SENSEX"]


@tool
async def get_period_returns(portfolio_id: str, user_id: str, benchmark: str = "SP500") -> dict:
    """Get multi-period returns comparison."""
    async for db in get_db():
        result = await benchmark_engine.calculate_benchmark_comparison(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            benchmark_override=benchmark,
            lookback_days=252,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


# ── Health Score Tools ──────────────────────────────────────────────────────

@tool
async def get_health_score(portfolio_id: str, user_id: str) -> dict:
    """Get overall portfolio health score with subscores."""
    async for db in get_db():
        result = await health_service.calculate_portfolio_health(
            db, portfolio_id=portfolio_id, user_id=user_id
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_subscores(portfolio_id: str, user_id: str) -> dict:
    """Get detailed subscore breakdown."""
    async for db in get_db():
        result = await health_service.calculate_portfolio_health(
            db, portfolio_id=portfolio_id, user_id=user_id
        )
        data = result.model_dump() if hasattr(result, 'model_dump') else result
        return data.get("subscores", {})


# ── Optimization Tools ──────────────────────────────────────────────────────

@tool
async def run_optimization(
    portfolio_id: str,
    user_id: str,
    method: str = "max_sharpe",
    constraints: Optional[dict] = None,
    lookback_days: int = 252,
    risk_free_rate: float = 0.05,
) -> dict:
    """Run portfolio optimization with specified method."""
    async for db in get_db():
        from app.schemas.optimization import OptimizationRequest, OptimizationConstraints
        
        opt_constraints = OptimizationConstraints(**(constraints or {}))
        request = OptimizationRequest(
            method=method,
            constraints=opt_constraints,
            lookback_days=lookback_days,
            risk_free_rate=risk_free_rate,
        )
        
        result = await optimization_engine.run_optimization(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            request=request,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_efficient_frontier(portfolio_id: str, user_id: str) -> dict:
    """Get efficient frontier data points for visualization."""
    async for db in get_db():
        # get_optimization_history returns List[OptimizationResponseData] pydantic objects
        result = await optimization_engine.get_optimization_history(db, portfolio_id, user_id, limit=1)
        if result and len(result) > 0:
            ef = getattr(result[0], "efficient_frontier", None)
            return ef.model_dump() if ef is not None and hasattr(ef, "model_dump") else (ef or {})
        return {}


# ── Stress Testing Tools ────────────────────────────────────────────────────

@tool
async def run_stress_test(
    portfolio_id: str,
    user_id: str,
    scenarios: Optional[List[str]] = None,
) -> dict:
    """Run stress test scenarios on portfolio."""
    async for db in get_db():
        from app.schemas.stress_test import StressTestRequest
        
        request = StressTestRequest(scenarios=scenarios or [
            "gfc_2008", "covid_2020", "high_inflation_2022", "rate_shock_2022"
        ])
        
        result = await stress_testing_engine.run_stress_test(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            request=request,
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result


@tool
async def get_scenarios() -> list[dict]:
    """Get list of available stress test scenarios."""
    return stress_testing_engine.get_available_scenarios()


# ── News & Sentiment Tools ─────────────────────────────────────────────────

@tool
async def get_portfolio_news(portfolio_id: str, user_id: str, days: int = 7) -> list[dict]:
    """Get recent news for portfolio holdings."""
    # This would be implemented in Phase 11
    return []


@tool
async def get_ticker_news(ticker: str, days: int = 7) -> list[dict]:
    """Get recent news for a specific ticker."""
    return []


@tool
async def get_sentiment(ticker: str, days: int = 7) -> dict:
    """Get sentiment score for a ticker."""
    return {"ticker": ticker, "sentiment": "neutral", "confidence": 0.5, "impact_score": 0.0}


@tool
async def get_sentiment_trend(ticker: str, days: int = 30) -> list[dict]:
    """Get sentiment trend over time."""
    return []


@tool
async def get_earnings_calendar(portfolio_id: str, user_id: str) -> list[dict]:
    """Get upcoming earnings for portfolio holdings."""
    return []


# ── Diversification Tools ──────────────────────────────────────────────────

@tool
async def get_concentration_metrics(portfolio_id: str, user_id: str) -> dict:
    """Get portfolio concentration metrics (HHI, top-N weight)."""
    async for db in get_db():
        portfolio = await _get_portfolio(db, portfolio_id, user_id)
        weights = [float(h.weight) for h in portfolio.holdings if h.weight]
        
        # Herfindahl-Hirschman Index
        hhi = sum(w ** 2 for w in weights)
        
        # Top 5 weight
        top5 = sum(sorted(weights, reverse=True)[:5])
        
        return {
            "hhi": round(hhi, 4),
            "top5_weight": round(top5, 4),
            "num_holdings": len(weights),
            "max_weight": round(max(weights) if weights else 0, 4),
        }


@tool
async def get_correlation_matrix(portfolio_id: str, user_id: str, lookback_days: int = 252) -> dict:
    """Get pairwise correlation matrix for portfolio holdings."""
    async for db in get_db():
        result = await risk_engine.calculate_portfolio_risk(
            db=db,
            portfolio_id=portfolio_id,
            user_id=user_id,
            lookback_days=lookback_days,
        )
        # Extract correlation data from risk engine if available
        return {"correlations": {}, "note": "Correlation matrix available in risk metrics"}


# ── Performance Attribution Tools ──────────────────────────────────────────

@tool
async def get_performance_attribution(
    portfolio_id: str,
    user_id: str,
    period: str = "1y",
) -> dict:
    """Get Brinson-style performance attribution."""
    # Would use performance attribution engine
    return {"attribution": {}, "note": "Performance attribution available via benchmark comparison"}


@tool
async def get_sector_returns(portfolio_id: str, user_id: str, period: str = "1y") -> dict:
    """Get per-sector returns."""
    return {"sector_returns": {}, "note": "Sector returns available in benchmark comparison"}


# ── Goal Planning Tools ────────────────────────────────────────────────────

@tool
async def run_goal_simulation(
    portfolio_id: str,
    user_id: str,
    target_amount: float,
    target_years: int,
    monthly_contribution: float = 0,
) -> dict:
    """Run Monte Carlo goal probability simulation."""
    return {
        "probability": 0.0,
        "projections": [],
        "note": "Goal planning simulation requires Phase 10 implementation",
    }


@tool
async def get_projections(portfolio_id: str, user_id: str, years: int = 10) -> dict:
    """Get wealth projections."""
    return {"projections": [], "note": "Projections require Phase 10 implementation"}


# ── Reporting Tools ────────────────────────────────────────────────────────

@tool
async def generate_report(
    portfolio_id: str,
    user_id: str,
    report_type: str = "full_portfolio",
    parameters: Optional[dict] = None,
) -> dict:
    """Trigger report generation (async)."""
    return {
        "report_id": str(uuid.uuid4()),
        "status": "generating",
        "note": "Report generation requires Phase 12 implementation",
    }


@tool
async def get_report_status(report_id: str) -> dict:
    """Check report generation status."""
    return {"status": "pending", "progress": 0, "note": "Reporting requires Phase 12 implementation"}


# Export all tools
TOOLS = [
    get_portfolio_summary,
    get_sector_allocation,
    get_risk_metrics,
    get_var_analysis,
    get_risk_contributions,
    get_return_series,
    get_benchmark_comparison,
    get_capture_ratios,
    get_benchmark_list,
    get_period_returns,
    get_health_score,
    get_subscores,
    run_optimization,
    get_efficient_frontier,
    run_stress_test,
    get_scenarios,
    get_portfolio_news,
    get_ticker_news,
    get_sentiment,
    get_sentiment_trend,
    get_earnings_calendar,
    get_concentration_metrics,
    get_correlation_matrix,
    get_performance_attribution,
    get_sector_returns,
    run_goal_simulation,
    get_projections,
    generate_report,
    get_report_status,
]