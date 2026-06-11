"""Tests for the Market Data Service and its API endpoints."""

import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.models.price_history import PriceHistory, ExchangeRate, CacheEntry
from app.models.user import User
from app.services import market_data_service, cache_service
from app.schemas.market_data import QuoteResponse, HistoryResponse, HistoryPriceItem, BenchmarkItem


# ── Fixtures & Mock Data ──────────────────────────────────────────────────


@pytest.fixture
def mock_yf_history():
    """Mock yfinance history DataFrame."""
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    dates.name = "Date"
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000000, 1100000, 1200000],
        },
        index=dates,
    )


@pytest.fixture
def mock_yf_info():
    """Mock yfinance info dictionary."""
    return {
        "longName": "Test Security Inc.",
        "sector": "Technology",
        "industry": "Software",
        "marketCap": 1500000000,
        "trailingPE": 25.5,
        "currency": "USD",
        "exchange": "NASDAQ",
    }


# ── Cache Service Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_service_store_and_retrieve(db_session: AsyncSession):
    """Verify in-memory and database-backed cache works correctly."""
    key = "test_key"
    val = {"data": "hello_world"}
    category = "test_cat"

    # Store
    await cache_service.set_cached_item(db_session, key, val, category, ttl_seconds=60)

    # Retrieve
    retrieved = await cache_service.get_cached_item(db_session, key)
    assert retrieved == val

    # Verify db persistence
    res = await db_session.execute(select(CacheEntry).where(CacheEntry.key == key))
    entry = res.scalar_one()
    assert entry.value == val

    # Delete
    await cache_service.delete_cached_item(db_session, key)
    retrieved_after_delete = await cache_service.get_cached_item(db_session, key)
    assert retrieved_after_delete is None


# ── Market Data Service Logic Tests ──────────────────────────────────────


@pytest.mark.asyncio
@patch("yfinance.Ticker")
async def test_get_quote_fetch_and_enrich(
    mock_ticker_class, mock_yf_info, mock_yf_history, db_session: AsyncSession
):
    """Verify get_quote calls provider, caches the response, and enriches instruments."""
    # Setup mock
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_yf_history
    mock_ticker.info = mock_yf_info
    mock_ticker_class.return_value = mock_ticker

    ticker = "AAPL"
    # Ensure instrument stub exists
    stub = Instrument(ticker=ticker, name=ticker, instrument_type="equity")
    db_session.add(stub)
    await db_session.commit()

    # Get Quote
    quote = await market_data_service.get_quote(db_session, ticker)

    assert quote.ticker == ticker
    assert quote.price == 104.0  # Last Close price in mock_yf_history
    assert quote.name == "Test Security Inc."
    assert quote.sector == "Technology"

    # Assert cache entry created
    cached_val = await cache_service.get_cached_item(db_session, f"quote:{ticker}")
    assert cached_val is not None
    assert cached_val["price"] == 104.0

    # Verify instrument was enriched
    await db_session.refresh(stub)
    assert stub.name == "Test Security Inc."
    assert stub.sector == "Technology"
    assert stub.market_cap == 1500000000


@pytest.mark.asyncio
@patch("yfinance.Ticker")
async def test_get_history_caches_prices_in_db(
    mock_ticker_class, mock_yf_history, db_session: AsyncSession
):
    """Verify get_history fetches from yfinance and persists prices into local DB table."""
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = mock_yf_history
    mock_ticker_class.return_value = mock_ticker

    ticker = "MSFT"
    history = await market_data_service.get_history(db_session, ticker, period="1mo")

    assert len(history.prices) == 3
    assert history.prices[0].close == 102.0

    res = await db_session.execute(
        select(PriceHistory).where(PriceHistory.ticker == "MSFT")
    )
    db_rows = list(res.scalars().all())
    assert len(db_rows) == 3
    assert float(db_rows[0].close) == 102.0
    assert db_rows[1].daily_return is not None  # computed return
    assert float(db_rows[1].daily_return) == pytest.approx((103.0 - 102.0) / 102.0)


@pytest.mark.asyncio
async def test_get_exchange_rate_fallback(db_session: AsyncSession):
    """Verify fallback and persistence of exchange rates."""
    rate_date = datetime.date(2024, 1, 15)

    # 1. Fetching same currency returns 1.0
    rate_same = await market_data_service.get_exchange_rate(db_session, "USD", "USD", rate_date)
    assert rate_same == 1.0

    # 2. Check fallback to CURRENCY_FALLBACKS constants
    rate_conv = await market_data_service.get_exchange_rate(db_session, "USD", "INR", rate_date)
    assert rate_conv == 83.50


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
@patch("app.services.market_data_service.get_exchange_rate")
async def test_portfolio_valuation_calculation(
    mock_exchange_rate, mock_get_history, db_session: AsyncSession
):
    """Verify portfolio valuation correctly aggregates prices, currencies, and forward-fills."""
    # Setup test user and portfolio
    user_id = datetime.datetime.now().microsecond  # unique mock identifier
    from app.services.auth_service import hash_password
    import uuid

    user = User(
        id=uuid.uuid4(),
        email=f"user_{user_id}@example.com",
        hashed_password=hash_password("SecurePass123!"),
        full_name="Mock User",
    )
    db_session.add(user)
    await db_session.flush()

    portfolio = Portfolio(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Test Val Portfolio",
        base_currency="USD",
        total_value=1000.0,
        total_cost=800.0,
    )
    db_session.add(portfolio)

    holding1 = Holding(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        ticker="AAPL",
        quantity=5.0,
        average_cost=100.0,
        current_price=120.0,
        current_value=600.0,
        cost_basis=500.0,
        currency="USD",
    )
    holding2 = Holding(
        id=uuid.uuid4(),
        portfolio_id=portfolio.id,
        ticker="INR_STOCK",
        quantity=10.0,
        average_cost=20.0,
        current_price=25.0,
        current_value=250.0,
        cost_basis=200.0,
        currency="INR",
    )
    db_session.add_all([holding1, holding2])
    await db_session.commit()

    # Mock get_history calls
    # 1. Benchmark index history timeline (dates: Jan 2, Jan 3)
    mock_bench_history = HistoryResponse(
        ticker="^GSPC",
        period="1y",
        interval="1d",
        prices=[
            HistoryPriceItem(date="2024-01-02", close=4000.0, adj_close=4000.0),
            HistoryPriceItem(date="2024-01-03", close=4010.0, adj_close=4010.0),
        ],
    )
    # 2. AAPL history
    mock_aapl_history = HistoryResponse(
        ticker="AAPL",
        period="1y",
        interval="1d",
        prices=[
            HistoryPriceItem(date="2024-01-02", close=100.0, adj_close=100.0),
            HistoryPriceItem(date="2024-01-03", close=102.0, adj_close=102.0),
        ],
    )
    # 3. INR_STOCK history (missing price on Jan 3 for forward-fill check)
    mock_inr_history = HistoryResponse(
        ticker="INR_STOCK",
        period="1y",
        interval="1d",
        prices=[
            HistoryPriceItem(date="2024-01-02", close=80.0, adj_close=80.0),
            # Missing Jan 3 close — should forward fill to 80.0
        ],
    )

    def get_history_side_effect(db, ticker, period="1y", interval="1d"):
        if ticker == "^GSPC":
            return mock_bench_history
        elif ticker == "AAPL":
            return mock_aapl_history
        elif ticker == "INR_STOCK":
            return mock_inr_history
        return HistoryResponse(ticker=ticker, period=period, interval=interval, prices=[])

    mock_get_history.side_effect = get_history_side_effect

    # Mock exchange rates (INR to USD: 0.012, USD to USD: 1.0)
    def exchange_rate_side_effect(db, from_curr, to_curr, rate_date):
        if from_curr.upper() == to_curr.upper():
            return 1.0
        return 0.012
    mock_exchange_rate.side_effect = exchange_rate_side_effect

    # Run Valuation
    val_resp = await market_data_service.get_portfolio_valuation_series(
        db_session, portfolio.id, user.id, period="1y"
    )

    assert val_resp.portfolio_id == portfolio.id
    assert len(val_resp.valuation_series) == 2

    # Check valuation on Jan 2:
    # AAPL: 5 shares * 100.0 = 500.0 USD
    # INR_STOCK: 10 shares * 80.0 INR = 800.0 INR * 0.012 = 9.6 USD
    # Total Jan 2 = 509.6
    assert val_resp.valuation_series[0].date == "2024-01-02"
    assert val_resp.valuation_series[0].value == 509.6

    # Check valuation on Jan 3:
    # AAPL: 5 shares * 102.0 = 510.0 USD
    # INR_STOCK: 10 shares * 80.0 (forward filled) = 800.0 INR * 0.012 = 9.6 USD
    # Total Jan 3 = 519.6
    assert val_resp.valuation_series[1].date == "2024-01-03"
    assert val_resp.valuation_series[1].value == 519.6


# ── API Endpoint Integration Tests ────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_quote")
async def test_get_quote_api_endpoint(mock_get_quote, registered_client):
    """Verify GET /api/v1/market-data/quote/{ticker} endpoints return HTTP 200."""
    client, headers, _ = registered_client

    mock_get_quote.return_value = QuoteResponse(
        ticker="AAPL",
        name="Apple Inc.",
        price=180.0,
        change=1.5,
        change_percent=0.84,
        currency="USD",
        last_updated=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    resp = await client.get("/api/v1/market-data/quote/AAPL", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "AAPL"
    assert data["price"] == 180.0


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_history")
async def test_get_history_api_endpoint(mock_get_history, registered_client):
    """Verify GET /api/v1/market-data/history/{ticker} endpoints return HTTP 200."""
    client, headers, _ = registered_client

    mock_get_history.return_value = HistoryResponse(
        ticker="MSFT",
        period="1mo",
        interval="1d",
        prices=[HistoryPriceItem(date="2024-01-02", close=350.0, adj_close=350.0)],
    )

    resp = await client.get(
        "/api/v1/market-data/history/MSFT?period=1mo&interval=1d", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "MSFT"
    assert len(data["prices"]) == 1


@pytest.mark.asyncio
@patch("app.services.market_data_service.get_benchmarks")
async def test_get_benchmarks_api_endpoint(mock_get_benchmarks, registered_client):
    """Verify GET /api/v1/benchmarks returns HTTP 200."""
    client, headers, _ = registered_client

    mock_get_benchmarks.return_value = [
        BenchmarkItem(
            id="SP500",
            name="S&P 500",
            ticker="^GSPC",
            currency="USD",
            current_value=4800.0,
            ytd_return=0.015,
            one_year_return=0.22,
        )
    ]

    resp = await client.get("/api/v1/benchmarks", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "SP500"
    assert data[0]["current_value"] == 4800.0
