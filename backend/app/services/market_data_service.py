"""Market data service — fetches and caches quotes, history, exchange rates, and portfolio valuations using yfinance."""

import asyncio
from uuid import UUID
from datetime import date, datetime, timezone
import pandas as pd
import yfinance as yf
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.instrument import Instrument
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.price_history import PriceHistory, Dividend, Split, ExchangeRate
from app.schemas.market_data import (
    QuoteResponse,
    HistoryPriceItem,
    HistoryResponse,
    ValuationSeriesItem,
    ValuationResponse,
    ReturnsSeriesItem,
    ReturnsResponse,
    BenchmarkItem,
)
from app.services import cache_service, portfolio_service
from app.utils.constants import BenchmarkType, CurrencyCode

# Fallback exchange rates if API fails
CURRENCY_FALLBACKS = {
    ("USD", "INR"): 83.50,
    ("INR", "USD"): 1.0 / 83.50,
    ("USD", "EUR"): 0.92,
    ("EUR", "USD"): 1.0 / 0.92,
    ("USD", "GBP"): 0.79,
    ("GBP", "USD"): 1.0 / 0.79,
    ("EUR", "INR"): 90.50,
    ("INR", "EUR"): 1.0 / 90.50,
}


async def get_quote(db: AsyncSession, ticker: str) -> QuoteResponse:
    """Get real-time quote. Cache for 15 minutes."""
    cache_key = f"quote:{ticker.upper()}"
    cached = await cache_service.get_cached_item(db, cache_key)
    if cached:
        return QuoteResponse.model_validate(cached)

    # Fetch from provider (run blocking yfinance call in executor)
    ticker_upper = ticker.upper()
    loop = asyncio.get_event_loop()
    try:
        quote_data = await loop.run_in_executor(None, _fetch_quote_from_provider, ticker_upper)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error fetching quote for ticker '{ticker_upper}': {str(e)}",
        )

    # Save to cache
    await cache_service.set_cached_item(db, cache_key, quote_data, "quotes", 900)  # 15 mins

    # Enrich instrument table if it exists
    await _enrich_instrument_by_ticker(db, ticker_upper, quote_data)

    return QuoteResponse.model_validate(quote_data)


async def get_history(
    db: AsyncSession, ticker: str, period: str = "1y", interval: str = "1d"
) -> HistoryResponse:
    """Get historical prices. Cache metadata, cache prices in DB."""
    ticker_upper = ticker.upper()
    cache_key = f"history_status:{ticker_upper}:{period}:{interval}"
    cached_status = await cache_service.get_cached_item(db, cache_key)

    # If cache status exists, load historical data from local DB
    if cached_status:
        db_prices = await _load_prices_from_db(db, ticker_upper, period)
        if db_prices:
            return HistoryResponse(
                ticker=ticker_upper,
                period=period,
                interval=interval,
                prices=[HistoryPriceItem.model_validate(p) for p in db_prices],
            )

    # Otherwise, fetch from yfinance
    loop = asyncio.get_event_loop()
    try:
        prices_list = await loop.run_in_executor(
            None, _fetch_history_from_provider, ticker_upper, period, interval
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error fetching history for ticker '{ticker_upper}': {str(e)}",
        )

    # Persist prices to DB
    await _persist_prices_to_db(db, ticker_upper, prices_list)

    # Mark history as cached for 12 hours
    await cache_service.set_cached_item(
        db, cache_key, {"status": "loaded", "count": len(prices_list)}, "market_data", 43200
    )

    return HistoryResponse(ticker=ticker_upper, period=period, interval=interval, prices=prices_list)


async def enrich_instrument(db: AsyncSession, instrument: Instrument) -> Instrument:
    """Enrich an existing Instrument object with yfinance data."""
    ticker = instrument.ticker.upper()
    try:
        quote = await get_quote(db, ticker)
        instrument.name = quote.name or instrument.name
        instrument.sector = quote.sector or instrument.sector
        instrument.industry = quote.industry or instrument.industry
        instrument.market_cap = quote.market_cap or instrument.market_cap
        instrument.currency = quote.currency or instrument.currency
        await db.flush()
    except Exception:
        # Ignore errors so stub is kept
        pass
    return instrument


async def get_exchange_rate(db: AsyncSession, from_curr: str, to_curr: str, rate_date: date) -> float:
    """Get exchange rate for a given date. Cache permanently if date is historical."""
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr == to_curr:
        return 1.0

    # Check database
    result = await db.execute(
        select(ExchangeRate).where(
            and_(
                ExchangeRate.from_currency == from_curr,
                ExchangeRate.to_currency == to_curr,
                ExchangeRate.date == rate_date,
            )
        )
    )
    rate_row = result.scalar_one_or_none()
    if rate_row:
        return float(rate_row.rate)

    # Query yfinance (blocking)
    pair = f"{from_curr}{to_curr}=X"
    loop = asyncio.get_event_loop()
    try:
        rate = await loop.run_in_executor(None, _fetch_rate_from_provider, pair, rate_date)
        if rate:
            # Persist rate to database
            rate_entry = ExchangeRate(
                from_currency=from_curr, to_currency=to_curr, date=rate_date, rate=rate
            )
            db.add(rate_entry)
            await db.flush()
            return rate
    except Exception:
        pass

    # Fallback 1: last available rate in database prior to rate_date
    result = await db.execute(
        select(ExchangeRate)
        .where(
            and_(
                ExchangeRate.from_currency == from_curr,
                ExchangeRate.to_currency == to_curr,
                ExchangeRate.date <= rate_date,
            )
        )
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    )
    fallback_row = result.scalar_one_or_none()
    if fallback_row:
        return float(fallback_row.rate)

    # Fallback 2: Hardcoded constant fallbacks
    rate = CURRENCY_FALLBACKS.get((from_curr, to_curr))
    if rate:
        return rate

    # Fallback 3: inverse of the reverse rate if it exists
    rate_rev = CURRENCY_FALLBACKS.get((to_curr, from_curr))
    if rate_rev:
        return 1.0 / rate_rev

    return 1.0


async def get_portfolio_valuation_series(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID, period: str = "1y"
) -> ValuationResponse:
    """Calculate historical portfolio value over time."""
    portfolio = await portfolio_service.get_portfolio_detail(db, portfolio_id, user_id)

    # 1. Fetch benchmark timeline to establish trading days
    benchmark_ticker = _get_benchmark_ticker(portfolio.benchmark)
    benchmark_history = await get_history(db, benchmark_ticker, period)
    trading_dates = [datetime.strptime(p.date, "%Y-%m-%d").date() for p in benchmark_history.prices]

    if not trading_dates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Benchmark trading timeline could not be loaded",
        )

    # 2. Fetch price histories for all tickers in portfolio
    holdings = portfolio.holdings
    holding_histories = {}
    for h in holdings:
        hist = await get_history(db, h.ticker, period)
        # map date -> adj_close
        holding_histories[h.ticker] = {
            datetime.strptime(p.date, "%Y-%m-%d").date(): p.adj_close for p in hist.prices
        }

    # 3. Calculate portfolio aggregate value per date
    valuation_series = []
    base_currency = portfolio.base_currency

    for d in trading_dates:
        total_val = 0.0
        for h in holdings:
            hist_map = holding_histories.get(h.ticker, {})
            price = hist_map.get(d)

            # Forward fill price if missing (e.g. trading holiday mismatch)
            if price is None:
                past_dates = [dt for dt in hist_map.keys() if dt <= d]
                if past_dates:
                    price = hist_map[max(past_dates)]
                else:
                    price = float(h.average_cost)  # Fallback to purchase cost

            # Convert to base currency
            rate = await get_exchange_rate(db, h.currency, base_currency, d)
            converted_price = price * rate
            total_val += float(h.quantity) * converted_price

        valuation_series.append(
            ValuationSeriesItem(date=d.isoformat(), value=round(total_val, 2))
        )

    current_val = float(portfolio.total_value)
    total_cost = float(portfolio.total_cost)
    total_return = (current_val - total_cost) / total_cost if total_cost > 0 else 0.0
    total_return_amount = current_val - total_cost

    return ValuationResponse(
        portfolio_id=portfolio.id,
        current_value=current_val,
        period=period,
        valuation_series=valuation_series,
        total_return=total_return,
        total_return_amount=total_return_amount,
    )


async def get_portfolio_returns_series(
    db: AsyncSession, portfolio_id: UUID, user_id: UUID, period: str = "1y"
) -> ReturnsResponse:
    """Calculate portfolio returns series over time."""
    val_resp = await get_portfolio_valuation_series(db, portfolio_id, user_id, period)
    v_series = val_resp.valuation_series

    returns_series = []
    for i in range(len(v_series)):
        if i == 0:
            returns_series.append(ReturnsSeriesItem(date=v_series[i].date, daily_return=0.0))
        else:
            prev_val = v_series[i - 1].value
            curr_val = v_series[i].value
            daily_ret = (curr_val - prev_val) / prev_val if prev_val > 0 else 0.0
            returns_series.append(ReturnsSeriesItem(date=v_series[i].date, daily_return=daily_ret))

    cumulative_return = val_resp.total_return

    # Annualized return estimation
    days = len(v_series)
    years = days / 252.0 if days > 0 else 1.0
    annualized_return = (1.0 + cumulative_return) ** (1.0 / years) - 1.0 if cumulative_return > -1.0 else -1.0

    return ReturnsResponse(
        portfolio_id=portfolio_id,
        period=period,
        returns=returns_series,
        cumulative_return=cumulative_return,
        annualized_return=annualized_return,
    )


async def get_benchmarks(db: AsyncSession) -> list[BenchmarkItem]:
    """Get active benchmark index values and metrics."""
    benchmarks_list = [
        {"id": "SP500", "name": "S&P 500", "ticker": "^GSPC", "currency": "USD"},
        {"id": "NASDAQ100", "name": "Nasdaq 100", "ticker": "^NDX", "currency": "USD"},
        {"id": "NIFTY50", "name": "Nifty 50", "ticker": "^NSEI", "currency": "INR"},
        {"id": "SENSEX", "name": "Sensex", "ticker": "^BSESN", "currency": "INR"},
    ]

    items = []
    for b in benchmarks_list:
        quote = await get_quote(db, b["ticker"])
        # Fetch history to compute YTD / 1Y returns
        hist = await get_history(db, b["ticker"], "1y")
        prices = hist.prices

        ytd_ret = 0.0
        one_yr_ret = 0.0

        if len(prices) >= 2:
            first_price = prices[0].adj_close
            last_price = prices[-1].adj_close
            one_yr_ret = (last_price - first_price) / first_price

            # Find start of year date index
            curr_year = datetime.now().year
            ytd_prices = [p for p in prices if datetime.strptime(p.date, "%Y-%m-%d").year == curr_year]
            if ytd_prices:
                ytd_start_price = ytd_prices[0].adj_close
                ytd_ret = (last_price - ytd_start_price) / ytd_start_price

        items.append(
            BenchmarkItem(
                id=b["id"],
                name=b["name"],
                ticker=b["ticker"],
                currency=b["currency"],
                current_value=quote.price,
                ytd_return=ytd_ret,
                one_year_return=one_yr_ret,
            )
        )

    return items


# ── Internal Fetching Providers (Blocking I/O ran in threadpool) ────────


def _fetch_quote_from_provider(ticker: str) -> dict:
    """Fetch quote from yfinance in blocking mode."""
    t = yf.Ticker(ticker)
    hist_2d = t.history(period="2d")

    if hist_2d.empty:
        raise ValueError(f"Ticker '{ticker}' returned empty data")

    price = float(hist_2d["Close"].iloc[-1])
    change = 0.0
    change_percent = 0.0
    if len(hist_2d) >= 2:
        prev_close = float(hist_2d["Close"].iloc[-2])
        change = price - prev_close
        change_percent = (change / prev_close) * 100

    volume = int(hist_2d["Volume"].iloc[-1]) if "Volume" in hist_2d else None

    # Load info metadata with graceful fallback
    try:
        info = t.info
        name = info.get("longName") or info.get("shortName") or ticker
        sector = info.get("sector")
        industry = info.get("industry")
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        currency = info.get("currency") or "USD"
        exchange = info.get("exchange")
    except Exception:
        name = ticker
        sector = None
        industry = None
        market_cap = None
        pe_ratio = None
        currency = "USD"
        exchange = None

    return {
        "ticker": ticker,
        "name": name,
        "price": price,
        "change": change,
        "change_percent": change_percent,
        "volume": volume,
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
        "sector": sector,
        "industry": industry,
        "currency": currency.upper(),
        "exchange": exchange,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_history_from_provider(ticker: str, period: str, interval: str) -> list[HistoryPriceItem]:
    """Fetch historical prices from yfinance in blocking mode."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No history found for ticker '{ticker}'")

    prices = []
    # Reset index to make 'Date' a column
    df = df.reset_index()

    for _, row in df.iterrows():
        # Handle index date format depending on timezone
        raw_date = row["Date"]
        if isinstance(raw_date, datetime):
            date_str = raw_date.date().isoformat()
        else:
            date_str = str(raw_date)[:10]

        adj_close = float(row["Close"])  # yfinance returns adjusted close automatically in history
        prices.append(
            HistoryPriceItem(
                date=date_str,
                open=float(row["Open"]) if "Open" in row else None,
                high=float(row["High"]) if "High" in row else None,
                low=float(row["Low"]) if "Low" in row else None,
                close=float(row["Close"]),
                adj_close=adj_close,
                volume=int(row["Volume"]) if "Volume" in row else None,
            )
        )
    return prices


def _fetch_rate_from_provider(pair: str, rate_date: date) -> float | None:
    """Fetch exchange rate from yfinance in blocking mode."""
    t = yf.Ticker(pair)
    # Query rate history around rate_date
    start_str = rate_date.isoformat()
    end_date = rate_date + timedelta(days=5)  # Fetch small buffer
    df = t.history(start=start_str, end=end_date.isoformat())

    if not df.empty:
        return float(df["Close"].iloc[0])
    return None


def _get_benchmark_ticker(benchmark: str | None) -> str:
    """Get yfinance ticker for benchmark enum."""
    if benchmark == BenchmarkType.SP500.value:
        return "^GSPC"
    elif benchmark == BenchmarkType.NASDAQ100.value:
        return "^NDX"
    elif benchmark == BenchmarkType.NIFTY50.value:
        return "^NSEI"
    elif benchmark == BenchmarkType.SENSEX.value:
        return "^BSESN"
    return "^GSPC"


# ── Local Database Caching Helpers ─────────────────────────────────────


async def _load_prices_from_db(db: AsyncSession, ticker: str, period: str) -> list[PriceHistory]:
    """Load cached prices from database."""
    # Convert period string to start_date
    days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "3y": 1095, "5y": 1825, "max": 9999}
    days = days_map.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(PriceHistory)
        .where(and_(PriceHistory.ticker == ticker, PriceHistory.date >= start_date))
        .order_by(PriceHistory.date.asc())
    )
    return list(result.scalars().all())


async def _persist_prices_to_db(db: AsyncSession, ticker: str, prices: list[HistoryPriceItem]) -> None:
    """Bulk upsert prices to database."""
    for i, p in enumerate(prices):
        p_date = datetime.strptime(p.date, "%Y-%m-%d").date()

        # Calculate daily return from previous row
        daily_return = None
        if i > 0:
            prev_close = prices[i - 1].adj_close
            daily_return = (p.adj_close - prev_close) / prev_close if prev_close > 0 else 0.0

        # Check if row exists
        result = await db.execute(
            select(PriceHistory).where(
                and_(PriceHistory.ticker == ticker, PriceHistory.date == p_date)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.open = p.open
            existing.high = p.high
            existing.low = p.low
            existing.close = p.close
            existing.adj_close = p.adj_close
            existing.volume = p.volume
            existing.daily_return = daily_return
        else:
            entry = PriceHistory(
                ticker=ticker,
                date=p_date,
                open=p.open,
                high=p.high,
                low=p.low,
                close=p.close,
                adj_close=p.adj_close,
                volume=p.volume,
                daily_return=daily_return,
            )
            db.add(entry)

    await db.flush()


async def _enrich_instrument_by_ticker(db: AsyncSession, ticker: str, quote: dict) -> None:
    """Enrich Instrument entry when a quote is successfully loaded."""
    result = await db.execute(select(Instrument).where(Instrument.ticker == ticker))
    inst = result.scalar_one_or_none()
    if inst:
        inst.name = quote.get("name") or inst.name
        inst.sector = quote.get("sector") or inst.sector
        inst.industry = quote.get("industry") or inst.industry
        inst.market_cap = quote.get("market_cap") or inst.market_cap
        inst.currency = quote.get("currency") or inst.currency
        await db.flush()
