"""Tests for the Stress Testing Engine service and API endpoints."""

import datetime
from unittest.mock import patch
import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.models.stress_test_result import StressTestResult
from app.models.user import User
from app.schemas.market_data import HistoryPriceItem, HistoryResponse
from app.schemas.stress_test import (
    HoldingImpact,
    SectorImpact,
    StressTestRequest,
)
from app.services import stress_testing_engine


def make_mock_history(ticker: str, dates: list, prices: list) -> HistoryResponse:
    """Create a mock history response for testing."""
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
        email="stress@example.com",
        hashed_password="pw",
        full_name="Stress Test User",
        risk_free_rate=0.04,
    )
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(
        user_id=user.id,
        name="Stress Test Portfolio",
        total_value=100000.0,
        total_cost=80000.0,
        benchmark="SP500",
        base_currency="USD",
    )
    db_session.add(portfolio)
    await db_session.flush()

    # Add instruments
    inst_aapl = Instrument(
        ticker="AAPL", name="Apple Inc.", instrument_type="equity", sector="Technology"
    )
    inst_msft = Instrument(
        ticker="MSFT", name="Microsoft Corp.", instrument_type="equity", sector="Technology"
    )
    inst_jpm = Instrument(
        ticker="JPM", name="JPMorgan Chase & Co.", instrument_type="equity", sector="Financial"
    )
    inst_xom = Instrument(
        ticker="XOM", name="Exxon Mobil Corporation", instrument_type="equity", sector="Energy"
    )
    db_session.add_all([inst_aapl, inst_msft, inst_jpm, inst_xom])
    await db_session.flush()

    # Add holdings
    h1 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_aapl.id,
        ticker="AAPL",
        quantity=200.0,
        average_cost=150.0,
        current_price=180.0,
        current_value=36000.0,
        weight=0.36,
        currency="USD",
    )
    h2 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_msft.id,
        ticker="MSFT",
        quantity=100.0,
        average_cost=300.0,
        current_price=350.0,
        current_value=35000.0,
        weight=0.35,
        currency="USD",
    )
    h3 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_jpm.id,
        ticker="JPM",
        quantity=150.0,
        average_cost=100.0,
        current_price=120.0,
        current_value=18000.0,
        weight=0.18,
        currency="USD",
    )
    h4 = Holding(
        portfolio_id=portfolio.id,
        instrument_id=inst_xom.id,
        ticker="XOM",
        quantity=100.0,
        average_cost=90.0,
        current_price=110.0,
        current_value=11000.0,
        weight=0.11,
        currency="USD",
    )
    db_session.add_all([h1, h2, h3, h4])
    await db_session.flush()

    # Generate synthetic price data for testing
    base_date = datetime.date(2024, 1, 1)
    dates = [base_date + datetime.timedelta(days=i) for i in range(100)]

    np.random.seed(42)
    ret_aapl = np.random.normal(0.0008, 0.012, 100)
    ret_msft = np.random.normal(0.0010, 0.010, 100)
    ret_jpm = np.random.normal(0.0005, 0.015, 100)
    ret_xom = np.random.normal(0.0003, 0.018, 100)
    ret_sp500 = np.random.normal(0.0005, 0.008, 100)

    p_aapl = 150.0 * np.cumprod(1.0 + ret_aapl)
    p_msft = 300.0 * np.cumprod(1.0 + ret_msft)
    p_jpm = 100.0 * np.cumprod(1.0 + ret_jpm)
    p_xom = 90.0 * np.cumprod(1.0 + ret_xom)
    p_sp500 = 4500.0 * np.cumprod(1.0 + ret_sp500)

    hist_map = {
        "AAPL": make_mock_history("AAPL", dates, p_aapl),
        "MSFT": make_mock_history("MSFT", dates, p_msft),
        "JPM": make_mock_history("JPM", dates, p_jpm),
        "XOM": make_mock_history("XOM", dates, p_xom),
        "^GSPC": make_mock_history("^GSPC", dates, p_sp500),
    }

    return user, portfolio, hist_map


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_scenario_execution(mock_get_history, db_session: AsyncSession):
    """Test running a single stress test scenario."""
    import numpy as np
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    request = StressTestRequest(scenarios=["gfc_2008"])
    
    result = await stress_testing_engine.run_stress_test(
        db_session, str(portfolio.id), str(user.id), request
    )
    
    assert result.status == "success"
    assert len(result.data.scenarios) == 1
    scenario_result = result.data.scenarios[0]
    assert scenario_result.scenario == "gfc_2008"
    assert isinstance(scenario_result.portfolio_return, float)
    assert isinstance(scenario_result.max_drawdown, float)
    assert scenario_result.recovery_days is not None
    assert len(scenario_result.holding_impacts) == 4
    assert len(scenario_result.sector_impacts) > 0
    assert isinstance(scenario_result.summary, str) and len(scenario_result.summary) > 0


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_multiple_scenarios(mock_get_history, db_session: AsyncSession):
    """Test running multiple stress test scenarios."""
    import numpy as np
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    request = StressTestRequest(scenarios=["gfc_2008", "covid_2020"])
    
    result = await stress_testing_engine.run_stress_test(
        db_session, str(portfolio.id), str(user.id), request
    )
    
    assert result.status == "success"
    assert len(result.data.scenarios) == 2
    scenario_ids = [s.scenario for s in result.data.scenarios]
    assert "gfc_2008" in scenario_ids
    assert "covid_2020" in scenario_ids


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_scenario_listing(mock_get_history, db_session: AsyncSession):
    """Test listing available stress test scenarios."""
    import numpy as np
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    scenarios = stress_testing_engine.get_available_scenarios()
    
    assert len(scenarios) == 4
    scenario_ids = [s.id for s in scenarios]
    assert "gfc_2008" in scenario_ids
    assert "covid_2020" in scenario_ids
    assert "high_inflation_2022" in scenario_ids
    assert "rate_shock_2022" in scenario_ids
    
    # Check that each scenario has required fields
    for scenario in scenarios:
        assert scenario.id
        assert scenario.name
        assert scenario.start_date
        assert scenario.end_date
        assert isinstance(scenario.sp500_return, float)
        assert scenario.description


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_history_retrieval(mock_get_history, db_session: AsyncSession):
    """Test retrieving stress test history."""
    import numpy as np
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # Run a stress test to create history
    request = StressTestRequest(scenarios=["gfc_2008"])
    await stress_testing_engine.run_stress_test(
        db_session, str(portfolio.id), str(user.id), request
    )

    # Retrieve history
    history = await stress_testing_engine.get_stress_test_history(
        db_session, str(portfolio.id), str(user.id), limit=10
    )
    
    assert len(history) >= 1
    history_item = history[0]
    assert "id" in history_item
    assert history_item["scenario"] == "gfc_2008"
    assert isinstance(history_item["portfolio_return"], float)
    assert isinstance(history_item["max_drawdown"], float)
    assert history_item["recovery_days"] is not None
    assert isinstance(history_item["summary"], str)


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_different_scenario_types(mock_get_history, db_session: AsyncSession):
    """Test that different scenario types produce different results."""
    import numpy as np
    import datetime
    
    user, portfolio, _ = await setup_portfolio_and_assets(db_session)
    
    # Create different mock histories for different periods
    # The engine requests different periods for different scenarios
    base_date = datetime.date(2024, 1, 1)
    dates_6mo = [base_date + datetime.timedelta(days=i) for i in range(180)]
    dates_1y = [base_date + datetime.timedelta(days=i) for i in range(365)]
    dates_2y = [base_date + datetime.timedelta(days=i) for i in range(730)]
    
    np.random.seed(42)
    # Different returns for different scenarios
    ret_gfc = np.random.normal(-0.001, 0.02, 365)  # 1y for GFC
    ret_covid = np.random.normal(-0.002, 0.03, 180)  # 6mo for COVID
    ret_inflation = np.random.normal(-0.0005, 0.015, 365)  # 1y for inflation
    ret_rate = np.random.normal(0.0002, 0.01, 730)  # 2y for rate shock
    
    p_gfc = 150.0 * np.cumprod(1.0 + ret_gfc)
    p_covid = 150.0 * np.cumprod(1.0 + ret_covid)
    p_inflation = 150.0 * np.cumprod(1.0 + ret_inflation)
    p_rate = 150.0 * np.cumprod(1.0 + ret_rate)
    p_sp500_1y = 4500.0 * np.cumprod(1.0 + np.random.normal(0.0003, 0.01, 365))
    p_sp500_6mo = 4500.0 * np.cumprod(1.0 + np.random.normal(0.0001, 0.008, 180))
    p_sp500_2y = 4500.0 * np.cumprod(1.0 + np.random.normal(0.0002, 0.008, 730))
    
    def make_hist(ticker, dates, prices):
        from app.schemas.market_data import HistoryPriceItem, HistoryResponse
        items = []
        for d, p in zip(dates, prices):
            d_str = d.isoformat() if isinstance(d, datetime.date) else str(d)
            items.append(HistoryPriceItem(
                date=d_str, open=float(p), high=float(p*1.01), low=float(p*0.99),
                close=float(p), adj_close=float(p), volume=1000
            ))
        return HistoryResponse(ticker=ticker, period="1y", interval="1d", prices=items)
    
    # Build hist_map with different data for different periods
    hist_map = {
        "AAPL": {
            "6mo": make_hist("AAPL", dates_6mo, p_covid[:180]),
            "1y": make_hist("AAPL", dates_1y, p_gfc),
            "2y": make_hist("AAPL", dates_2y, p_rate),
        },
        "MSFT": {
            "6mo": make_hist("MSFT", dates_6mo, p_covid[:180] * 2),
            "1y": make_hist("MSFT", dates_1y, p_gfc * 2),
            "2y": make_hist("MSFT", dates_2y, p_rate * 2),
        },
        "JPM": {
            "6mo": make_hist("JPM", dates_6mo, p_covid[:180] * 0.8),
            "1y": make_hist("JPM", dates_1y, p_gfc * 0.8),
            "2y": make_hist("JPM", dates_2y, p_rate * 0.8),
        },
        "XOM": {
            "6mo": make_hist("XOM", dates_6mo, p_covid[:180] * 0.7),
            "1y": make_hist("XOM", dates_1y, p_gfc * 0.7),
            "2y": make_hist("XOM", dates_2y, p_rate * 0.7),
        },
        "^GSPC": {
            "6mo": make_hist("^GSPC", dates_6mo, p_sp500_6mo),
            "1y": make_hist("^GSPC", dates_1y, p_sp500_1y),
            "2y": make_hist("^GSPC", dates_2y, p_sp500_2y),
        },
    }
    
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(ticker, {}).get(period, hist_map["^GSPC"]["1y"])

    # Run all four scenarios
    request = StressTestRequest(scenarios=["gfc_2008", "covid_2020", "high_inflation_2022", "rate_shock_2022"])
    result = await stress_testing_engine.run_stress_test(
        db_session, str(portfolio.id), str(user.id), request
    )
    
    assert result.status == "success"
    assert len(result.data.scenarios) == 4
    
    # Each scenario should have different characteristics
    returns = [s.portfolio_return for s in result.data.scenarios]
    # At least some should be different (they use different historical periods)
    assert len(set([round(r, 3) for r in returns])) > 1  # At least 2 different returns when rounded to 3 decimals


@pytest.mark.asyncio
async def test_stress_test_empty_portfolio(db_session: AsyncSession):
    """Test stress testing with empty portfolio raises appropriate error."""
    user = User(
        email="empty@example.com",
        hashed_password="pw",
        full_name="Empty Portfolio User",
        risk_free_rate=0.04,
    )
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(
        user_id=user.id,
        name="Empty Portfolio",
        total_value=0.0,
        total_cost=0.0,
        benchmark="SP500",
        base_currency="USD",
    )
    db_session.add(portfolio)
    await db_session.flush()
    # No holdings added

    request = StressTestRequest(scenarios=["gfc_2008"])
    
    with pytest.raises(Exception) as exc_info:
        await stress_testing_engine.run_stress_test(
            db_session, str(portfolio.id), str(user.id), request
        )
    
    assert "no active holdings" in str(exc_info.value).lower() or "holdings" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_invalid_scenario(
    mock_get_history, db_session: AsyncSession
):
    """Test that invalid scenario ID raises appropriate error."""
    import numpy as np
    from pydantic import ValidationError
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )

    # Pydantic validates at schema level with Literal types
    with pytest.raises(ValidationError) as exc_info:
        StressTestRequest(scenarios=["invalid_scenario_123"])
    
    assert "invalid_scenario_123" in str(exc_info.value)


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_stress_test_api_endpoints(
    mock_get_history, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Test stress testing API endpoints."""
    import numpy as np
    
    user, portfolio, hist_map = await setup_portfolio_and_assets(db_session)
    mock_get_history.side_effect = lambda db, ticker, period: hist_map.get(
        ticker, hist_map["^GSPC"]
    )
    
    # Associate portfolio with auth user
    u_res = await db_session.execute(select(User).limit(1))
    auth_user = u_res.scalar_one()
    portfolio.user_id = auth_user.id
    await db_session.commit()

    # 1. POST /portfolios/{id}/stress-test
    payload = {
        "scenarios": ["gfc_2008", "covid_2020"]
    }
    r = await client.post(
        f"/api/v1/portfolios/{portfolio.id}/stress-test",
        json=payload,
        headers=auth_headers,
    )
    assert r.status_code == 200
    res_data = r.json()
    assert res_data["status"] == "success"
    assert len(res_data["data"]["scenarios"]) == 2
    scenario_ids = [s["scenario"] for s in res_data["data"]["scenarios"]]
    assert "gfc_2008" in scenario_ids
    assert "covid_2020" in scenario_ids

    # 2. GET /stress-test/scenarios
    r_scenarios = await client.get(
        "/api/v1/portfolios/stress-test/scenarios",
        headers=auth_headers,
    )
    assert r_scenarios.status_code == 200
    scenarios_data = r_scenarios.json()["data"]
    assert len(scenarios_data) == 4
    scenario_ids = [s["id"] for s in scenarios_data]
    assert "gfc_2008" in scenario_ids
    assert "covid_2020" in scenario_ids

    # 3. GET /portfolios/{id}/stress-test/history
    r_history = await client.get(
        f"/api/v1/portfolios/{portfolio.id}/stress-test/history",
        headers=auth_headers,
    )
    assert r_history.status_code == 200
    history_data = r_history.json()["data"]
    assert len(history_data) >= 1
    history_item = history_data[0]
    assert history_item["scenario"] in ["gfc_2008", "covid_2020"]