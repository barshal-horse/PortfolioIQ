"""Tests for the Portfolio Health Score service and its API endpoints."""

import datetime
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.models.health_score import HealthScore
from app.models.risk_metrics import RiskMetrics
from app.models.benchmark_comparison import BenchmarkComparison
from app.models.user import User
from app.schemas.market_data import HistoryResponse, HistoryPriceItem
from app.schemas.health import HealthScoreResponse, RefreshResponse
from app.services import health_service
from app.schemas.risk import RiskResponse, RiskMetricsDetails, SeriesData
from app.schemas.benchmark import (
    BenchmarkComparisonResponse,
    BenchmarkMetrics,
    PeriodReturns,
    PeriodReturnItem,
    ComparisonSeries,
)

# ── Mocking Helpers ───────────────────────────────────────────────────────

def create_mock_holding_history(ticker, dates, start_price, pct_change):
    prices = []
    curr = start_price
    for d in dates:
        prices.append(
            HistoryPriceItem(
                date=d.isoformat() if isinstance(d, datetime.date) else d,
                open=curr,
                high=curr,
                low=curr,
                close=curr,
                adj_close=curr,
                volume=100
            )
        )
        curr *= (1.0 + pct_change)
    return HistoryResponse(ticker=ticker, period="1y", interval="1d", prices=prices)


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
@patch("app.services.risk_engine.calculate_portfolio_risk")
@patch("app.services.benchmark_engine.calculate_benchmark_comparison")
async def test_calculate_portfolio_health_service_on_the_fly(
    mock_calc_bench,
    mock_calc_risk,
    mock_get_history,
    db_session: AsyncSession,
):
    """Test health score calculations when metrics are not cached in DB (calculated on-the-fly)."""
    # Create test user
    user = User(email="health@example.com", hashed_password="pw", full_name="Health User")
    db_session.add(user)
    await db_session.flush()

    # Create portfolio
    portfolio = Portfolio(
        user_id=user.id,
        name="Health Portfolio",
        total_value=10000.0,
        total_cost=9000.0,
        benchmark="SP500",
        base_currency="USD"
    )
    db_session.add(portfolio)
    await db_session.flush()

    # Add instruments and holdings
    inst1 = Instrument(ticker="AAPL", name="Apple Inc.", instrument_type="equity", sector="Technology", country="US")
    inst2 = Instrument(ticker="MSFT", name="Microsoft Corp.", instrument_type="equity", sector="Technology", country="US")
    db_session.add_all([inst1, inst2])
    await db_session.flush()

    h1 = Holding(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        quantity=50.0,
        average_cost=100.0,
        current_price=100.0,
        current_value=5000.0,
        weight=0.50,
        currency="USD",
        instrument_id=inst1.id
    )
    h2 = Holding(
        portfolio_id=portfolio.id,
        ticker="MSFT",
        quantity=20.0,
        average_cost=250.0,
        current_price=250.0,
        current_value=5000.0,
        weight=0.50,
        currency="USD",
        instrument_id=inst2.id
    )
    db_session.add_all([h1, h2])
    await db_session.flush()

    # Mock historical daily dates
    t_dates = [datetime.date(2024, 1, i) for i in range(1, 11)]
    t_date_strs = [d.isoformat() for d in t_dates]

    # Return series for risk engine
    # Generate mock daily returns
    p_returns = [0.001] * 10

    # Mock get_history for assets
    mock_get_history.side_effect = lambda db, ticker, period: (
        create_mock_holding_history("AAPL", t_dates, 100.0, 0.01)
        if ticker == "AAPL"
        else create_mock_holding_history("MSFT", t_dates, 250.0, -0.01)
    )

    # Mock on-the-fly calculations
    mock_calc_risk.return_value = RiskResponse(
        portfolio_id=portfolio.id,
        calculation_date=datetime.datetime.now(datetime.timezone.utc),
        lookback_days=252,
        risk_free_rate=0.05,
        benchmark="SP500",
        metrics=RiskMetricsDetails(
            annualized_return=0.10,
            annualized_volatility=0.15,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            beta=1.0,
            alpha=0.0,
            information_ratio=0.5,
            tracking_error=0.08,
            max_drawdown=-0.12,
            max_drawdown_start=t_date_strs[0],
            max_drawdown_end=t_date_strs[-1],
            current_drawdown=-0.02,
            var_95=-0.01,
            var_99=-0.02,
            cvar_95=-0.015,
            cvar_99=-0.025,
            downside_deviation=0.10,
            calmar_ratio=0.83,
            skewness=0.0,
            kurtosis=3.0,
        ),
        return_series=SeriesData(dates=t_date_strs, values=p_returns),
        drawdown_series=SeriesData(dates=t_date_strs, values=[-0.02] * 10),
    )

    mock_calc_bench.return_value = BenchmarkComparisonResponse(
        portfolio_id=portfolio.id,
        calculation_date=datetime.datetime.now(datetime.timezone.utc),
        benchmark="SP500",
        lookback_days=252,
        metrics=BenchmarkMetrics(
            active_return=0.02,
            tracking_error=0.08,
            information_ratio=0.25,
            beta=1.0,
            alpha=0.0,
            upside_capture=1.05,
            downside_capture=0.98,
            correlation=0.92,
        ),
        period_returns=PeriodReturns(
            **{
                "1m": PeriodReturnItem(portfolio=0.01, benchmark=0.01),
                "3m": PeriodReturnItem(portfolio=0.03, benchmark=0.025),
                "6m": PeriodReturnItem(portfolio=0.06, benchmark=0.05),
                "1y": PeriodReturnItem(portfolio=0.10, benchmark=0.08),
                "ytd": PeriodReturnItem(portfolio=0.05, benchmark=0.04),
            }
        ),
        cumulative_comparison=ComparisonSeries(
            dates=t_date_strs,
            portfolio=[1.0] * 10,
            benchmark=[1.0] * 10,
        ),
        rolling_alpha=SeriesData(dates=t_date_strs, values=[0.0] * 10),
        rolling_beta=SeriesData(dates=t_date_strs, values=[1.0] * 10),
        rolling_correlation=SeriesData(dates=t_date_strs, values=[0.9] * 10),
    )

    # Execute health score calculation
    health_resp = await health_service.calculate_portfolio_health(
        db_session, portfolio.id, user.id
    )

    # Asserts
    assert health_resp.portfolio_id == portfolio.id
    assert health_resp.overall.score > 0
    assert health_resp.overall.grade in ["excellent", "good", "fair", "poor", "critical"]
    assert health_resp.subscores.diversification.score > 0
    assert health_resp.subscores.risk.score > 0
    assert health_resp.subscores.performance.score > 0
    assert health_resp.subscores.efficiency.score > 0

    # Verify db caching
    res = await db_session.execute(
        select(HealthScore).where(HealthScore.portfolio_id == portfolio.id)
    )
    db_entry = res.scalar_one()
    assert db_entry.overall_score == health_resp.overall.score
    assert db_entry.overall_grade == health_resp.overall.grade
    assert len(db_entry.recommendations) > 0


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_calculate_portfolio_health_service_cached(
    mock_get_history,
    db_session: AsyncSession,
):
    """Test health score calculations using cached database risk metrics and benchmark comparisons."""
    # Create test user
    user = User(email="cached_health@example.com", hashed_password="pw", full_name="Cached Health User")
    db_session.add(user)
    await db_session.flush()

    # Create portfolio
    portfolio = Portfolio(
        user_id=user.id,
        name="Cached Health Portfolio",
        total_value=10000.0,
        total_cost=9000.0,
        benchmark="SP500",
        base_currency="USD"
    )
    db_session.add(portfolio)
    await db_session.flush()

    # Add instruments and holdings
    inst1 = Instrument(ticker="AAPL", name="Apple Inc.", instrument_type="equity", sector="Technology", country="US")
    db_session.add(inst1)
    await db_session.flush()

    h1 = Holding(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        quantity=100.0,
        average_cost=100.0,
        current_price=100.0,
        current_value=10000.0,
        weight=1.0,
        currency="USD",
        instrument_id=inst1.id
    )
    db_session.add(h1)
    await db_session.flush()

    # Insert cached RiskMetrics and BenchmarkComparison
    t_dates = [(datetime.date(2024, 1, 1) + datetime.timedelta(days=i)).isoformat() for i in range(10)]
    
    cached_risk = RiskMetrics(
        portfolio_id=portfolio.id,
        lookback_days=252,
        annualized_return=0.12,
        annualized_volatility=0.18,
        sharpe_ratio=0.8,
        sortino_ratio=1.0,
        beta=1.1,
        alpha=0.01,
        information_ratio=0.2,
        tracking_error=0.06,
        max_drawdown=-0.15,
        cvar_95=-0.02,
        return_series={"dates": t_dates, "values": [0.001] * 10},
        drawdown_series={"dates": t_dates, "values": [-0.01] * 10},
    )
    db_session.add(cached_risk)

    cached_bench = BenchmarkComparison(
        portfolio_id=portfolio.id,
        benchmark="SP500",
        lookback_days=252,
        active_return=0.02,
        tracking_error=0.06,
        information_ratio=0.2,
        beta=1.1,
        alpha=0.01,
    )
    db_session.add(cached_bench)
    await db_session.flush()

    # Mock historical daily pricing (average correlation will default/be computed)
    mock_get_history.return_value = create_mock_holding_history("AAPL", t_dates, 100.0, 0.0)

    # Compute
    health_resp = await health_service.calculate_portfolio_health(
        db_session, portfolio.id, user.id
    )

    assert health_resp.portfolio_id == portfolio.id
    assert health_resp.overall.score > 0
    assert health_resp.subscores.diversification.details["num_holdings"] == 1


# ── API Endpoint Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.health_service.calculate_portfolio_health")
async def test_get_portfolio_health_api(mock_calc_health, registered_client):
    """Verify GET /portfolios/{id}/health routes successfully."""
    client, headers, user_id = registered_client

    import uuid
    pid = uuid.uuid4()

    mock_calc_health.return_value = HealthScoreResponse(
        portfolio_id=pid,
        calculation_date=datetime.datetime.now(datetime.timezone.utc),
        overall={"score": 85, "grade": "excellent", "explanation": "Perfect score"},
        subscores={
            "diversification": {"score": 90, "grade": "excellent", "weight": 0.25, "details": {}},
            "risk": {"score": 80, "grade": "excellent", "weight": 0.30, "details": {}},
            "performance": {"score": 85, "grade": "excellent", "weight": 0.25, "details": {}},
            "efficiency": {"score": 85, "grade": "excellent", "weight": 0.20, "details": {}},
        },
        recommendations=[]
    )

    resp = await client.get(f"/api/v1/portfolios/{pid}/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["overall"]["score"] == 85
    assert data["overall"]["grade"] == "excellent"


@pytest.mark.asyncio
@patch("app.services.health_service.calculate_portfolio_health")
async def test_refresh_portfolio_health_api(mock_calc_health, registered_client):
    """Verify POST /portfolios/{id}/health/refresh routes and triggers recalculation."""
    client, headers, user_id = registered_client

    import uuid
    pid = uuid.uuid4()

    resp = await client.post(f"/api/v1/portfolios/{pid}/health/refresh", headers=headers)
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert "recalculation started" in data["message"]
    mock_calc_health.assert_called_once()
