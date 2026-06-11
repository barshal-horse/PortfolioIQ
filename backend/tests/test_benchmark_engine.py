"""Tests for the Benchmark Engine service and its API endpoints."""

import datetime
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio
from app.models.benchmark_comparison import BenchmarkComparison
from app.models.user import User
from app.schemas.market_data import ValuationResponse, ValuationSeriesItem, HistoryResponse, HistoryPriceItem
from app.schemas.benchmark import BenchmarkComparisonResponse, BenchmarkMetrics, PeriodReturns, ComparisonSeries, PeriodReturnItem
from app.schemas.risk import SeriesData
from app.services import benchmark_engine
from tests.test_risk_engine import create_mock_valuation_response, create_mock_benchmark_history


# ── Service Logic Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.market_data_service.get_portfolio_valuation_series")
@patch("app.services.market_data_service.get_history")
async def test_calculate_benchmark_comparison_service(
    mock_get_history,
    mock_get_valuation,
    db_session: AsyncSession,
):
    """Test standard benchmark comparison calculations for mathematical correctness."""
    # Create test user
    user = User(email="bench@example.com", hashed_password="pw", full_name="Bench User", risk_free_rate=0.05)
    db_session.add(user)
    await db_session.flush()

    # Create portfolio
    portfolio = Portfolio(user_id=user.id, name="Bench Portfolio", total_value=100000.0, total_cost=80000.0)
    db_session.add(portfolio)
    await db_session.flush()

    # Stub Mock services
    # Let's mock a 70-day series so rolling window calculations (W = 60) can execute successfully
    mock_get_valuation.return_value = create_mock_valuation_response(portfolio.id, 100000.0, 0.005, num_days=70)
    mock_get_history.return_value = create_mock_benchmark_history("^GSPC", 5000.0, 0.003, num_days=70)

    # Compute comparison
    comp_resp = await benchmark_engine.calculate_benchmark_comparison(
        db_session, portfolio.id, user.id, benchmark_override="SP500", lookback_days=70
    )

    # Check metrics existence & bounds
    assert comp_resp.portfolio_id == portfolio.id
    assert comp_resp.benchmark == "SP500"
    assert comp_resp.metrics.active_return > 0.0  # portfolio grew faster (0.5% vs 0.3% daily)
    assert comp_resp.metrics.upside_capture is not None
    assert comp_resp.metrics.downside_capture is not None
    
    # Check rolling statistics existence
    assert len(comp_resp.rolling_alpha.values) > 0
    assert len(comp_resp.rolling_beta.values) > 0
    assert len(comp_resp.rolling_correlation.values) > 0
    
    # Check period returns
    assert comp_resp.period_returns.one_month.portfolio > 0.0
    assert comp_resp.period_returns.one_month.benchmark > 0.0

    # Verify db persistence of metrics
    res = await db_session.execute(
        select(BenchmarkComparison).where(BenchmarkComparison.portfolio_id == portfolio.id)
    )
    db_entry = res.scalar_one()
    assert float(db_entry.active_return) == pytest.approx(comp_resp.metrics.active_return)
    assert float(db_entry.beta) == pytest.approx(comp_resp.metrics.beta)


# ── API Endpoint Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.benchmark_engine.calculate_benchmark_comparison")
async def test_get_portfolio_benchmark_api(mock_calc_comp, registered_client):
    """Verify GET /portfolios/{id}/benchmark calls service layer and returns structured JSON."""
    client, headers, user = registered_client

    import uuid
    pid = uuid.uuid4()

    mock_calc_comp.return_value = BenchmarkComparisonResponse(
        portfolio_id=pid,
        benchmark="SP500",
        calculation_date=datetime.datetime.now(datetime.timezone.utc),
        lookback_days=252,
        metrics=BenchmarkMetrics(
            active_return=0.05,
            tracking_error=0.06,
            information_ratio=0.83,
            alpha=0.04,
            beta=1.1,
            upside_capture=110.0,
            downside_capture=95.0,
        ),
        period_returns=PeriodReturns(
            one_month=PeriodReturnItem(portfolio=0.03, benchmark=0.02),
            three_month=PeriodReturnItem(portfolio=0.08, benchmark=0.06),
            six_month=PeriodReturnItem(portfolio=0.15, benchmark=0.12),
            one_year=PeriodReturnItem(portfolio=0.25, benchmark=0.20),
            ytd=PeriodReturnItem(portfolio=0.05, benchmark=0.04),
        ),
        cumulative_comparison=ComparisonSeries(
            dates=["2024-01-02"],
            portfolio=[1.03],
            benchmark=[1.02],
        ),
        rolling_alpha=SeriesData(dates=["2024-01-02"], values=[0.04]),
        rolling_beta=SeriesData(dates=["2024-01-02"], values=[1.1]),
        rolling_correlation=SeriesData(dates=["2024-01-02"], values=[0.85]),
    )

    resp = await client.get(f"/api/v1/portfolios/{pid}/benchmark?lookback_days=252", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["portfolio_id"] == str(pid)
    assert data["benchmark"] == "SP500"
    assert data["metrics"]["active_return"] == 0.05
    assert data["period_returns"]["1m"]["portfolio"] == 0.03
    assert data["rolling_correlation"]["values"] == [0.85]
