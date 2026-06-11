"""Tests for the Risk Engine service and its API endpoints."""

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
from app.models.risk_metrics import RiskMetrics
from app.models.user import User
from app.schemas.market_data import ValuationResponse, ValuationSeriesItem, HistoryResponse, HistoryPriceItem
from app.schemas.risk import (
    RiskResponse,
    RiskMetricsDetails,
    VaRResponse,
    RiskContributionsResponse,
    HoldingRiskContribution,
    SeriesData,
)
from app.services import risk_engine


# ── Mocking Helpers ───────────────────────────────────────────────────────

def create_mock_valuation_response(portfolio_id, start_value, daily_change_pct, num_days=20):
    """Generate a mock ValuationResponse with deterministic pricing trend."""
    series = []
    base_date = datetime.date(2024, 1, 1)
    current_value = start_value

    for i in range(num_days):
        d_str = (base_date + datetime.timedelta(days=i)).isoformat()
        if i > 0:
            current_value *= (1.0 + daily_change_pct)
        series.append(ValuationSeriesItem(date=d_str, value=round(current_value, 2)))

    return ValuationResponse(
        portfolio_id=portfolio_id,
        current_value=series[-1].value,
        period="1y",
        valuation_series=series,
        total_return=(series[-1].value - start_value) / start_value if start_value > 0 else 0.0,
        total_return_amount=series[-1].value - start_value,
    )


def create_mock_benchmark_history(ticker, start_value, daily_change_pct, num_days=20):
    """Generate a mock HistoryResponse for index ticker."""
    prices = []
    base_date = datetime.date(2024, 1, 1)
    current_value = start_value

    for i in range(num_days):
        d_str = (base_date + datetime.timedelta(days=i)).isoformat()
        if i > 0:
            current_value *= (1.0 + daily_change_pct)
        prices.append(
            HistoryPriceItem(
                date=d_str,
                open=current_value * 0.99,
                high=current_value * 1.01,
                low=current_value * 0.98,
                close=current_value,
                adj_close=current_value,
                volume=100000,
            )
        )

    return HistoryResponse(ticker=ticker, period="1y", interval="1d", prices=prices)


# ── Service Logic Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.market_data_service.get_portfolio_valuation_series")
@patch("app.services.market_data_service.get_history")
async def test_calculate_portfolio_risk_service(
    mock_get_history,
    mock_get_valuation,
    db_session: AsyncSession,
):
    """Test standard portfolio risk calculations for arithmetic correctness."""
    # Create test user
    user = User(email="risk@example.com", hashed_password="pw", full_name="Risk User", risk_free_rate=0.04)
    db_session.add(user)
    await db_session.flush()

    # Create portfolio
    portfolio = Portfolio(user_id=user.id, name="Risk Portfolio", total_value=100000.0, total_cost=80000.0)
    db_session.add(portfolio)
    await db_session.flush()

    # Stub Mock services
    # Portfolio increases 1% daily, benchmark increases 0.5% daily
    mock_get_valuation.return_value = create_mock_valuation_response(portfolio.id, 100000.0, 0.01, num_days=30)
    mock_get_history.return_value = create_mock_benchmark_history("^GSPC", 5000.0, 0.005, num_days=30)

    # Compute risk
    risk_resp = await risk_engine.calculate_portfolio_risk(
        db_session, portfolio.id, user.id, lookback_days=30, rf_override=0.04
    )

    # Check metrics existence & bounds
    assert risk_resp.portfolio_id == portfolio.id
    assert risk_resp.metrics.annualized_return > 0.0
    assert risk_resp.metrics.annualized_volatility > 0.0
    assert risk_resp.metrics.sharpe_ratio is not None
    assert risk_resp.metrics.max_drawdown == 0.0  # value went straight up
    assert risk_resp.metrics.var_95 is not None
    assert risk_resp.metrics.var_99 is not None

    # Verify db persistence of metrics
    res = await db_session.execute(
        select(RiskMetrics).where(RiskMetrics.portfolio_id == portfolio.id)
    )
    db_entry = res.scalar_one()
    assert float(db_entry.sharpe_ratio) == pytest.approx(risk_resp.metrics.sharpe_ratio)
    assert float(db_entry.risk_free_rate) == pytest.approx(0.04)


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_portfolio_valuation_series")
async def test_calculate_var_details(mock_get_valuation, db_session: AsyncSession):
    """Test Historical, Parametric, and Monte Carlo VaR methods."""
    user = User(email="var@example.com", hashed_password="pw", full_name="VaR User")
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(user_id=user.id, name="VaR Portfolio", total_value=100000.0)
    db_session.add(portfolio)
    await db_session.flush()

    # Valuation fluctuates up and down
    # Return series: [0.02, -0.03, 0.01, -0.02, 0.03, -0.01, ...]
    mock_series = []
    base_date = datetime.date(2024, 1, 1)
    values = [100000.0, 102000.0, 98940.0, 99929.4, 97930.8, 100868.7, 99860.0, 100000.0]
    for i, v in enumerate(values):
        mock_series.append(ValuationSeriesItem(date=(base_date + datetime.timedelta(days=i)).isoformat(), value=v))

    mock_get_valuation.return_value = ValuationResponse(
        portfolio_id=portfolio.id,
        current_value=values[-1],
        period="1y",
        valuation_series=mock_series,
        total_return=0.0,
        total_return_amount=0.0,
    )

    # Test historical VaR
    hist_var = await risk_engine.calculate_var_details(
        db_session, portfolio.id, user.id, method="historical", confidence=0.90, horizon_days=1
    )
    assert hist_var.method == "historical"
    assert hist_var.confidence == 0.90
    assert hist_var.var < 0.0
    assert hist_var.var_amount < 0.0
    assert hist_var.cvar < hist_var.var

    # Test parametric VaR
    para_var = await risk_engine.calculate_var_details(
        db_session, portfolio.id, user.id, method="parametric", confidence=0.95, horizon_days=5
    )
    assert para_var.method == "parametric"
    assert para_var.horizon_days == 5
    assert para_var.var < 0.0

    # Test Monte Carlo VaR
    mc_var = await risk_engine.calculate_var_details(
        db_session, portfolio.id, user.id, method="monte_carlo", confidence=0.99, horizon_days=10
    )
    assert mc_var.method == "monte_carlo"
    assert mc_var.horizon_days == 10
    assert mc_var.var < 0.0


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_calculate_risk_contributions(mock_get_history, db_session: AsyncSession):
    """Test asset risk contributions / Euler decomposition calculation logic."""
    user = User(email="euler@example.com", hashed_password="pw", full_name="Euler User")
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(user_id=user.id, name="Euler Portfolio", total_value=10000.0)
    db_session.add(portfolio)
    await db_session.flush()

    # Add 2 holdings (AAPL and MSFT)
    h1 = Holding(portfolio_id=portfolio.id, ticker="AAPL", quantity=30.0, average_cost=150.0, current_price=160.0, current_value=4800.0, weight=0.48, currency="USD")
    h2 = Holding(portfolio_id=portfolio.id, ticker="MSFT", quantity=20.0, average_cost=250.0, current_price=260.0, current_value=5200.0, weight=0.52, currency="USD")
    db_session.add_all([h1, h2])
    await db_session.flush()

    # Mock histories
    dates = [datetime.date(2024, 1, i) for i in range(1, 11)]
    
    # AAPL prices going up 1% daily
    aapl_prices = [100.0 * (1.01 ** i) for i in range(10)]
    aapl_hist = HistoryResponse(
        ticker="AAPL", period="1y", interval="1d",
        prices=[HistoryPriceItem(date=d.isoformat(), open=p, high=p, low=p, close=p, adj_close=p, volume=1000) for d, p in zip(dates, aapl_prices)]
    )

    # MSFT prices going down 0.5% daily
    msft_prices = [200.0 * (0.995 ** i) for i in range(10)]
    msft_hist = HistoryResponse(
        ticker="MSFT", period="1y", interval="1d",
        prices=[HistoryPriceItem(date=d.isoformat(), open=p, high=p, low=p, close=p, adj_close=p, volume=1000) for d, p in zip(dates, msft_prices)]
    )

    # Benchmark timeline
    spy_prices = [400.0 * (1.001 ** i) for i in range(10)]
    spy_hist = HistoryResponse(
        ticker="^GSPC", period="1y", interval="1d",
        prices=[HistoryPriceItem(date=d.isoformat(), open=p, high=p, low=p, close=p, adj_close=p, volume=1000) for d, p in zip(dates, spy_prices)]
    )

    def mock_get_history_side_effect(db, ticker, period="1y"):
        if ticker == "AAPL":
            return aapl_hist
        elif ticker == "MSFT":
            return msft_hist
        else:
            return spy_hist

    mock_get_history.side_effect = mock_get_history_side_effect

    # Compute contributions
    contrib_resp = await risk_engine.calculate_risk_contributions(db_session, portfolio.id, user.id)

    assert contrib_resp.portfolio_volatility > 0.0
    assert len(contrib_resp.contributions) == 2
    
    # Assert contributions sum to portfolio volatility (approximate due to float representation)
    sum_rc = sum(c.weight * c.marginal_contribution for c in contrib_resp.contributions)
    assert abs(sum_rc - contrib_resp.portfolio_volatility) < 1e-4

    # Assert percentage risk contributions sum to 100%
    sum_pct = sum(c.percentage_contribution for c in contrib_resp.contributions)
    assert abs(sum_pct - 100.0) < 1e-2


# ── API Endpoint Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.risk_engine.calculate_portfolio_risk")
async def test_get_portfolio_risk_api(mock_calc_risk, registered_client):
    """Verify GET /portfolios/{id}/risk calls service layer and returns structured json."""
    client, headers, user = registered_client

    import uuid
    pid = uuid.uuid4()

    mock_calc_risk.return_value = RiskResponse(
        portfolio_id=pid,
        calculation_date=datetime.datetime.now(datetime.timezone.utc),
        lookback_days=252,
        risk_free_rate=0.05,
        benchmark="SP500",
        metrics=RiskMetricsDetails(annualized_return=0.15, sharpe_ratio=1.1, max_drawdown=-0.08),
        return_series=SeriesData(dates=["2024-01-02"], values=[0.015]),
        drawdown_series=SeriesData(dates=["2024-01-02"], values=[-0.01]),
    )

    resp = await client.get(f"/api/v1/portfolios/{pid}/risk", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["portfolio_id"] == str(pid)
    assert data["metrics"]["sharpe_ratio"] == 1.1
    assert data["metrics"]["max_drawdown"] == -0.08


@pytest.mark.asyncio
@patch("app.services.risk_engine.calculate_var_details")
async def test_get_portfolio_var_api(mock_calc_var, registered_client):
    """Verify GET /portfolios/{id}/risk/var works with query params."""
    client, headers, user = registered_client

    import uuid
    pid = uuid.uuid4()

    mock_calc_var.return_value = VaRResponse(
        method="historical",
        confidence=0.95,
        horizon_days=1,
        var=-0.02,
        var_amount=-2000.0,
        cvar=-0.025,
        cvar_amount=-2500.0,
        portfolio_value=100000.0,
        interpretation="Test interpretation string",
    )

    resp = await client.get(
        f"/api/v1/portfolios/{pid}/risk/var?method=historical&confidence=0.95&horizon_days=1",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["method"] == "historical"
    assert data["var"] == -0.02
    assert data["interpretation"] == "Test interpretation string"


@pytest.mark.asyncio
@patch("app.services.risk_engine.calculate_risk_contributions")
async def test_get_portfolio_risk_contributions_api(mock_calc_contrib, registered_client):
    """Verify GET /portfolios/{id}/risk/contributions returns holding breakdowns."""
    client, headers, user = registered_client

    import uuid
    pid = uuid.uuid4()

    mock_calc_contrib.return_value = RiskContributionsResponse(
        portfolio_volatility=0.18,
        contributions=[
            HoldingRiskContribution(
                ticker="AAPL",
                weight=0.60,
                individual_volatility=0.22,
                marginal_contribution=0.15,
                percentage_contribution=50.0,
                beta_to_portfolio=1.1,
            )
        ],
    )

    resp = await client.get(f"/api/v1/portfolios/{pid}/risk/contributions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["portfolio_volatility"] == 0.18
    assert len(data["contributions"]) == 1
    assert data["contributions"][0]["ticker"] == "AAPL"
