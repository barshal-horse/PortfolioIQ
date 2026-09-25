"""Tests for the Optimization Engine service and API endpoints."""

import datetime
from unittest.mock import patch
import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.optimization_run import OptimizationRun
from app.models.portfolio import Portfolio
from app.models.user import User
from app.schemas.market_data import HistoryPriceItem, HistoryResponse
from app.schemas.optimization import (
    BlackLittermanRequest,
    BlackLittermanView,
    OptimizationConstraints,
    OptimizationRequest,
)
from app.services import optimization_engine


def make_mock_history(ticker: str, dates: list, prices: list) -> HistoryResponse:
    items = []
    for d, p in zip(dates, prices):
        d_str = d.isoformat() if isinstance(d, datetime.date) else str(d)
        items.append(
            HistoryPriceItem(
                date=d_str,
                open=float(p),
                high=float(p * 1.01),
                low=float(p * 0.99),
                close=float(p),
                adj_close=float(p),
                volume=1000,
            )
        )
    return HistoryResponse(ticker=ticker, period="1y", interval="1d", prices=items)


async def setup_portfolio_and_assets(db_session: AsyncSession):
    """Fixture helper to create user, portfolio, instruments, and holdings."""
    user = User(
        email="quant@example.com",
        hashed_password="pw",
        full_name="Quant User",
        risk_free_rate=0.04,
    )
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(
        user_id=user.id,
        name="Tech & Growth",
        total_value=100000.0,
        total_cost=80000.0,
        benchmark="SP500",
        base_currency="USD",
    )
    db_session.add(portfolio)
    await db_session.flush()

    inst_aapl = Instrument(
        ticker="AAPL", name="Apple Inc.", instrument_type="equity", sector="Technology"
    )
    inst_msft = Instrument(
        ticker="MSFT", name="Microsoft Corp.", instrument_type="equity", sector="Technology"
    )
    inst_googl = Instrument(
        ticker="GOOGL", name="Alphabet Inc.", instrument_type="equity", sector="Communication"
    )
    db_session.add_all([inst_aapl, inst_msft, inst_googl])
    await db_session.flush()

    h1 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_aapl.id,
        ticker="AAPL",
        quantity=300.0,
        average_cost=150.0,
        current_price=180.0,
        current_value=54000.0,
        weight=0.54,
        currency="USD",
    )
    h2 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_msft.id,
        ticker="MSFT",
        quantity=80.0,
        average_cost=300.0,
        current_price=350.0,
        current_value=28000.0,
        weight=0.28,
        currency="USD",
    )
    h3 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_googl.id,
        ticker="GOOGL",
        quantity=130.0,
        average_cost=120.0,
        current_price=138.46,
        current_value=18000.0,
        weight=0.18,
        currency="USD",
    )
    db_session.add_all([h1, h2, h3])
    await db_session.flush()

    # Generate 100 days of synthetic trading prices
    base_date = datetime.date(2024, 1, 1)
    dates = [base_date + datetime.timedelta(days=i) for i in range(100)]

    np.random.seed(42)
    ret_aapl = np.random.normal(0.0008, 0.012, 100)
    ret_msft = np.random.normal(0.0010, 0.010, 100)
    ret_googl = np.random.normal(0.0006, 0.015, 100)
    ret_sp500 = np.random.normal(0.0005, 0.008, 100)

    p_aapl = 150.0 * np.cumprod(1.0 + ret_aapl)
    p_msft = 300.0 * np.cumprod(1.0 + ret_msft)
    p_googl = 120.0 * np.cumprod(1.0 + ret_googl)
    p_sp500 = 4500.0 * np.cumprod(1.0 + ret_sp500)

    hist_map = {
        "AAPL": make_mock_history("AAPL", dates, p_aapl),
        "MSFT": make_mock_history("MSFT", dates, p_msft),
        "GOOGL": make_mock_history("GOOGL", dates, p_googl),
        "^GSPC": make_mock_history("^GSPC", dates, p_sp500),
    }

    return user, portfolio, hist_map


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_optimization_max_sharpe(mock_get_history, db_session: AsyncSession):
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    req = OptimizationRequest(
        method="max_sharpe",
        lookback_days=252,
        risk_free_rate=0.04,
        constraints=OptimizationConstraints(min_weight=0.05, max_weight=0.80),
    )

    resp = await optimization_engine.run_optimization(
        db_session, str(portfolio.id), str(user.id), req
    )

    assert resp.status == "success"
    data = resp.data
    assert data.method == "max_sharpe"
    assert len(data.optimal_allocation) == 3
    total_opt_w = sum(data.optimal_allocation.values())
    assert pytest.approx(total_opt_w, rel=1e-2) == 1.0

    # Bounds respected
    for w in data.optimal_allocation.values():
        assert w >= 0.049
        assert w <= 0.81

    # Check metrics
    assert data.expected_metrics.expected_return > 0
    assert data.expected_metrics.expected_volatility > 0
    assert data.expected_metrics.expected_sharpe is not None
    assert data.current_metrics is not None

    # Check trades generated
    assert len(data.trades) == 3
    trade_tickers = {t.ticker for t in data.trades}
    assert trade_tickers == {"AAPL", "MSFT", "GOOGL"}

    # Check efficient frontier generated
    assert data.efficient_frontier is not None
    assert len(data.efficient_frontier.returns) > 0
    assert len(data.efficient_frontier.volatilities) == len(data.efficient_frontier.returns)

    # Check DB persistence
    res = await db_session.execute(
        select(OptimizationRun).where(OptimizationRun.id == data.id)
    )
    db_run = res.scalar_one_or_none()
    assert db_run is not None
    assert db_run.method == "max_sharpe"


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_optimization_min_variance_and_risk_parity(
    mock_get_history, db_session: AsyncSession
):
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # 1. Min variance
    req_min = OptimizationRequest(
        method="min_variance",
        lookback_days=252,
        risk_free_rate=0.04,
    )
    resp_min = await optimization_engine.run_optimization(
        db_session, str(portfolio.id), str(user.id), req_min
    )
    assert resp_min.status == "success"
    assert resp_min.data.method == "min_variance"
    assert pytest.approx(sum(resp_min.data.optimal_allocation.values()), rel=1e-2) == 1.0

    # 2. Risk parity
    req_rp = OptimizationRequest(
        method="risk_parity",
        lookback_days=252,
        risk_free_rate=0.04,
    )
    resp_rp = await optimization_engine.run_optimization(
        db_session, str(portfolio.id), str(user.id), req_rp
    )
    assert resp_rp.status == "success"
    assert resp_rp.data.method == "risk_parity"
    for w in resp_rp.data.optimal_allocation.values():
        assert w > 0.05  # Equal risk contribution gives all assets a positive slice


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_black_litterman_optimization(mock_get_history, db_session: AsyncSession):
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # Bullish view on GOOGL
    req_bl = BlackLittermanRequest(
        views=[
            BlackLittermanView(
                type="absolute",
                ticker="GOOGL",
                expected_return=0.35,
                confidence=0.9,
            ),
            BlackLittermanView(
                type="relative",
                long_ticker="MSFT",
                short_ticker="AAPL",
                expected_outperformance=0.08,
                confidence=0.7,
            ),
        ],
        constraints=OptimizationConstraints(min_weight=0.0, max_weight=1.0),
        lookback_days=252,
        risk_free_rate=0.04,
    )

    resp = await optimization_engine.run_black_litterman_optimization(
        db_session, str(portfolio.id), str(user.id), req_bl
    )

    assert resp.status == "success"
    data = resp.data
    assert data.method == "black_litterman"
    assert data.posterior_returns is not None
    assert "GOOGL" in data.posterior_returns
    assert len(data.views) == 2
    assert pytest.approx(sum(data.optimal_allocation.values()), rel=1e-2) == 1.0


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_optimization_api_endpoints(
    mock_get_history,
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # Get test user from auth_headers
    u_res = await db_session.execute(select(User).limit(1))
    auth_user = u_res.scalar_one()
    # Associate portfolio with auth_user
    portfolio.user_id = auth_user.id
    await db_session.commit()

    # 1. POST /optimize
    payload = {
        "method": "max_sharpe",
        "constraints": {"min_weight": 0.05, "max_weight": 0.70},
        "lookback_days": 252,
        "risk_free_rate": 0.05,
    }
    r = await client.post(
        f"/api/v1/portfolios/{portfolio.id}/optimize",
        json=payload,
        headers=auth_headers,
    )
    assert r.status_code == 200
    res_data = r.json()
    assert res_data["status"] == "success"
    assert res_data["data"]["method"] == "max_sharpe"
    assert "optimal_allocation" in res_data["data"]
    assert "trades" in res_data["data"]
    assert "efficient_frontier" in res_data["data"]

    # 2. POST /optimize/black-litterman
    bl_payload = {
        "views": [
            {
                "type": "absolute",
                "ticker": "AAPL",
                "expected_return": 0.20,
                "confidence": 0.8,
            }
        ],
        "constraints": {"min_weight": 0.02, "max_weight": 0.80},
    }
    r_bl = await client.post(
        f"/api/v1/portfolios/{portfolio.id}/optimize/black-litterman",
        json=bl_payload,
        headers=auth_headers,
    )
    assert r_bl.status_code == 200
    assert r_bl.json()["data"]["method"] == "black_litterman"

    # 3. GET /optimize/history
    r_hist = await client.get(
        f"/api/v1/portfolios/{portfolio.id}/optimize/history",
        headers=auth_headers,
    )
    assert r_hist.status_code == 200
    history_items = r_hist.json()["data"]
    assert len(history_items) >= 2


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_optimization_sector_constraints(mock_get_history, db_session: AsyncSession):
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # AAPL and MSFT are Technology. Constraint: max 40% Technology
    req = OptimizationRequest(
        method="max_sharpe",
        lookback_days=252,
        risk_free_rate=0.04,
        constraints=OptimizationConstraints(
            min_weight=0.0,
            max_weight=1.0,
            sector_limits={"Technology": 0.40},
        ),
    )

    resp = await optimization_engine.run_optimization(
        db_session, str(portfolio.id), str(user.id), req
    )
    assert resp.status == "success"
    opt_w = resp.data.optimal_allocation
    tech_sum = opt_w.get("AAPL", 0.0) + opt_w.get("MSFT", 0.0)
    assert tech_sum <= 0.41


@pytest.mark.asyncio
async def test_insufficient_holdings_raises_400(db_session: AsyncSession):
    user = User(email="single@example.com", hashed_password="pw", full_name="Solo")
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(
        user_id=user.id,
        name="Solo Portfolio",
        total_value=1000.0,
        benchmark="SP500",
        base_currency="USD",
    )
    db_session.add(portfolio)
    await db_session.flush()

    h = Holding(
        portfolio_id=portfolio.id,
        ticker="AAPL",
        quantity=10.0,
        average_cost=100.0,
        current_price=100.0,
        current_value=1000.0,
        weight=1.0,
    )
    db_session.add(h)
    await db_session.flush()

    with pytest.raises(Exception) as exc_info:
        await optimization_engine.run_optimization(
            db_session, str(portfolio.id), str(user.id), OptimizationRequest()
        )
    assert "Portfolio must contain at least 2 distinct active holdings" in str(exc_info.value)
