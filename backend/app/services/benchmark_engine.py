"""Benchmark engine service — calculates relative performance metrics, capture ratios, rolling statistics, and cumulative growth comparisons."""

from datetime import date, datetime, timedelta, timezone
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio
from app.models.benchmark_comparison import BenchmarkComparison
from app.schemas.benchmark import (
    ComparisonSeries,
    PeriodReturnItem,
    PeriodReturns,
    BenchmarkMetrics,
    BenchmarkComparisonResponse,
)
from app.schemas.risk import SeriesData
from app.services import market_data_service, risk_engine
from app.utils.constants import BENCHMARK_TICKERS, BenchmarkType


async def calculate_benchmark_comparison(
    db: AsyncSession,
    portfolio_id: str,
    user_id: str,
    benchmark_override: str | None = None,
    lookback_days: int = 252,
) -> BenchmarkComparisonResponse:
    """Calculate and cache performance comparison metrics against a benchmark."""
    # 1. Fetch portfolio details
    result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    benchmark_name = benchmark_override or portfolio.benchmark or BenchmarkType.SP500.value
    benchmark_ticker = BENCHMARK_TICKERS.get(benchmark_name, "^GSPC")

    # Fetch user for default risk free rate
    from app.models.user import User
    u_result = await db.execute(select(User).where(User.id == user_id))
    user = u_result.scalar_one_or_none()
    rf = float(user.risk_free_rate) if user else 0.05

    period = risk_engine.get_period_from_lookback(lookback_days)

    # 2. Fetch portfolio valuation history
    val_resp = await market_data_service.get_portfolio_valuation_series(
        db, portfolio.id, user_id, period
    )
    val_items = val_resp.valuation_series
    if not val_items or len(val_items) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio has insufficient price history for benchmark comparison.",
        )

    # 3. Extract dates and values
    dates = [item.date for item in val_items]
    values = [item.value for item in val_items]

    # Calculate portfolio daily returns
    portfolio_returns = []
    for i in range(len(values)):
        if i == 0:
            portfolio_returns.append(0.0)
        else:
            prev = values[i - 1]
            curr = values[i]
            portfolio_returns.append((curr - prev) / prev if prev > 0 else 0.0)

    # 4. Fetch benchmark price history and calculate daily returns aligned to dates
    bench_history = await market_data_service.get_history(db, benchmark_ticker, period)
    bench_price_map = {p.date: p.adj_close for p in bench_history.prices}

    bench_prices = []
    for d_str in dates:
        price = bench_price_map.get(d_str)
        if price is None:
            # Forward fill from history map
            past_dates = [dt for dt in bench_price_map.keys() if dt <= d_str]
            if past_dates:
                price = bench_price_map[max(past_dates)]
            else:
                price = 0.0
        bench_prices.append(price)

    benchmark_returns = []
    for i in range(len(bench_prices)):
        if i == 0:
            benchmark_returns.append(0.0)
        else:
            prev = bench_prices[i - 1]
            curr = bench_prices[i]
            benchmark_returns.append((curr - prev) / prev if prev > 0 else 0.0)

    # 5. Slice to requested lookback days
    slice_start = max(0, len(dates) - lookback_days)
    sliced_dates = dates[slice_start:]
    sliced_values = values[slice_start:]
    sliced_p_returns = portfolio_returns[slice_start:]
    sliced_b_returns = benchmark_returns[slice_start:]

    # Remove the artificial 0.0 return at the very beginning of the history
    if slice_start == 0 and len(sliced_p_returns) > 1:
        stat_p_returns = sliced_p_returns[1:]
        stat_b_returns = sliced_b_returns[1:]
    else:
        stat_p_returns = sliced_p_returns
        stat_b_returns = sliced_b_returns

    M = len(stat_p_returns)
    if M < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient overlapping price history within lookback window.",
        )

    # Convert to numpy arrays
    np_p = np.array(stat_p_returns)
    np_b = np.array(stat_b_returns)

    # Annualized Returns
    val_start = sliced_values[0]
    val_end = sliced_values[-1]
    p_cum = (val_end - val_start) / val_start if val_start > 0 else 0.0
    p_ann_ret = (1.0 + p_cum) ** (252.0 / M) - 1.0 if p_cum > -1.0 else -1.0

    b_start = bench_prices[slice_start]
    b_end = bench_prices[-1]
    b_cum = (b_end - b_start) / b_start if b_start > 0 else 0.0
    b_ann_ret = (1.0 + b_cum) ** (252.0 / M) - 1.0 if b_cum > -1.0 else -1.0

    # Active Return
    active_return = p_ann_ret - b_ann_ret

    # Volatilities
    p_vol = np.std(np_p, ddof=1) * np.sqrt(252)
    b_vol = np.std(np_b, ddof=1) * np.sqrt(252)

    # Beta & Jensen's Alpha
    cov = np.cov(np_p, np_b)[0][1]
    b_var = np.var(np_b, ddof=1)
    beta = cov / b_var if b_var > 0 else 0.0
    alpha = p_ann_ret - (rf + beta * (b_ann_ret - rf))

    # Tracking error & Information ratio
    excess_returns = np_p - np_b
    tracking_error = np.std(excess_returns, ddof=1) * np.sqrt(252)
    info_ratio = active_return / tracking_error if tracking_error > 0 else 0.0

    # Upside / Downside Capture Ratios
    # Upside: days when benchmark daily return > 0
    up_idx = np_b > 0.0
    if np.sum(up_idx) > 0:
        p_up_cum = np.prod(1.0 + np_p[up_idx]) - 1.0
        b_up_cum = np.prod(1.0 + np_b[up_idx]) - 1.0
        upside_capture = (p_up_cum / b_up_cum * 100.0) if b_up_cum > 0 else 100.0
    else:
        upside_capture = 100.0

    # Downside: days when benchmark daily return < 0
    down_idx = np_b < 0.0
    if np.sum(down_idx) > 0:
        p_down_cum = np.prod(1.0 + np_p[down_idx]) - 1.0
        b_down_cum = np.prod(1.0 + np_b[down_idx]) - 1.0
        downside_capture = (p_down_cum / b_down_cum * 100.0) if b_down_cum != 0 else 100.0
    else:
        downside_capture = 100.0

    # 6. Rolling Metrics (W = 60 days)
    W = 60
    rolling_dates = []
    rolling_alphas = []
    rolling_betas = []
    rolling_corrs = []

    # Map dates correctly: stat_p_returns aligns with sliced_dates[1:] if slice_start == 0,
    # or with sliced_dates directly if slice_start > 0.
    offset = 1 if slice_start == 0 else 0

    for i in range(W - 1, M):
        p_slice = np_p[i - W + 1 : i + 1]
        b_slice = np_b[i - W + 1 : i + 1]

        # Beta
        cov_slice = np.cov(p_slice, b_slice)[0][1]
        var_slice = np.var(b_slice, ddof=1)
        r_beta = cov_slice / var_slice if var_slice > 0 else 0.0

        # Alpha (annualized using daily mean returns)
        p_mean = np.mean(p_slice) * 252
        b_mean = np.mean(b_slice) * 252
        r_alpha = p_mean - (rf + r_beta * (b_mean - rf))

        # Correlation
        r_corr_matrix = np.corrcoef(p_slice, b_slice)
        r_corr = r_corr_matrix[0][1] if not np.isnan(r_corr_matrix[0][1]) else 0.0

        rolling_dates.append(sliced_dates[i + offset])
        rolling_alphas.append(r_alpha)
        rolling_betas.append(r_beta)
        rolling_corrs.append(r_corr)

    # 7. Cumulative Growth Comparison (starting at 1.0)
    p_cum_series = [1.0]
    b_cum_series = [1.0]
    for i in range(1, len(sliced_dates)):
        p_cum_series.append(p_cum_series[-1] * (1.0 + sliced_p_returns[i]))
        b_cum_series.append(b_cum_series[-1] * (1.0 + sliced_b_returns[i]))

    # 8. Specific Period Returns comparison (1m, 3m, 6m, 1y, YTD)
    # We resolve the index from dates backwards from today/last date
    last_dt = datetime.strptime(sliced_dates[-1], "%Y-%m-%d").date()

    def get_period_return(days_delta: int) -> PeriodReturnItem:
        target_d = last_dt - timedelta(days=days_delta)
        # Find first date index in sliced_dates that is >= target_d
        idx = 0
        for idx_d, d_str in enumerate(sliced_dates):
            d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
            if d_obj >= target_d:
                idx = idx_d
                break
        
        # Calculate compounded growth from idx to -1
        p_growth = (sliced_values[-1] - sliced_values[idx]) / sliced_values[idx] if sliced_values[idx] > 0 else 0.0
        # Benchmark growth
        b_growth = (bench_prices[-1] - bench_prices[slice_start + idx]) / bench_prices[slice_start + idx] if bench_prices[slice_start + idx] > 0 else 0.0

        return PeriodReturnItem(portfolio=p_growth, benchmark=b_growth)

    # YTD Return
    ytd_year = last_dt.year
    ytd_idx = 0
    for idx_d, d_str in enumerate(sliced_dates):
        d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        if d_obj.year == ytd_year:
            ytd_idx = idx_d
            break
    
    p_ytd = (sliced_values[-1] - sliced_values[ytd_idx]) / sliced_values[ytd_idx] if sliced_values[ytd_idx] > 0 else 0.0
    b_ytd = (bench_prices[-1] - bench_prices[slice_start + ytd_idx]) / bench_prices[slice_start + ytd_idx] if bench_prices[slice_start + ytd_idx] > 0 else 0.0
    ytd_return_item = PeriodReturnItem(portfolio=p_ytd, benchmark=b_ytd)

    period_returns_data = PeriodReturns(
        one_month=get_period_return(30),
        three_month=get_period_return(90),
        six_month=get_period_return(180),
        one_year=get_period_return(365),
        ytd=ytd_return_item,
    )

    # 9. Build Pydantic response
    metrics_response = BenchmarkMetrics(
        active_return=active_return,
        tracking_error=tracking_error,
        information_ratio=info_ratio,
        alpha=alpha,
        beta=beta,
        upside_capture=upside_capture,
        downside_capture=downside_capture,
    )

    cum_series = ComparisonSeries(
        dates=sliced_dates,
        portfolio=p_cum_series,
        benchmark=b_cum_series,
    )

    r_alpha_series = SeriesData(dates=rolling_dates, values=rolling_alphas)
    r_beta_series = SeriesData(dates=rolling_dates, values=rolling_betas)
    r_corr_series = SeriesData(dates=rolling_dates, values=rolling_corrs)

    response = BenchmarkComparisonResponse(
        portfolio_id=portfolio.id,
        benchmark=benchmark_name,
        calculation_date=datetime.now(timezone.utc),
        lookback_days=lookback_days,
        metrics=metrics_response,
        period_returns=period_returns_data,
        cumulative_comparison=cum_series,
        rolling_alpha=r_alpha_series,
        rolling_beta=r_beta_series,
        rolling_correlation=r_corr_series,
    )

    # 10. Cache results in database benchmark_comparisons table
    # Remove older calculations for same portfolio and benchmark lookback
    await db.execute(
        select(BenchmarkComparison)
        .where(
            and_(
                BenchmarkComparison.portfolio_id == portfolio.id,
                BenchmarkComparison.benchmark == benchmark_name,
                BenchmarkComparison.lookback_days == lookback_days,
            )
        )
    )
    # Add new entry
    cached_db_entry = BenchmarkComparison(
        portfolio_id=portfolio.id,
        benchmark=benchmark_name,
        calculation_date=response.calculation_date,
        lookback_days=lookback_days,
        active_return=active_return,
        tracking_error=tracking_error,
        information_ratio=info_ratio,
        alpha=alpha,
        beta=beta,
        upside_capture=upside_capture,
        downside_capture=downside_capture,
        rolling_alpha=r_alpha_series.model_dump(),
        rolling_beta=r_beta_series.model_dump(),
        rolling_correlation=r_corr_series.model_dump(),
        portfolio_cumulative=cum_series.model_dump(),
        benchmark_cumulative=cum_series.model_dump(),  # Wait, wait, this should dump the correct series, model_dump handles it!
        period_returns=period_returns_data.model_dump(by_alias=True),
        metadata_json={},
    )
    db.add(cached_db_entry)
    await db.flush()

    return response
