"""Risk engine service — calculates portfolio statistical risk metrics, tail risks, and risk contributions."""

import math
from datetime import date, datetime, timezone
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Portfolio
from app.models.holding import Holding
from app.models.risk_metrics import RiskMetrics
from app.schemas.risk import (
    RiskMetricsDetails,
    RiskResponse,
    VaRResponse,
    HoldingRiskContribution,
    RiskContributionsResponse,
    SeriesData,
)
from app.services import market_data_service
from app.utils.constants import BENCHMARK_TICKERS, BenchmarkType


def get_period_from_lookback(lookback_days: int) -> str:
    """Map lookback days to yfinance period strings."""
    if lookback_days <= 30:
        return "3mo"
    elif lookback_days <= 90:
        return "6mo"
    elif lookback_days <= 252:
        return "1y"
    elif lookback_days <= 504:
        return "3y"
    else:
        return "5y"


async def calculate_portfolio_risk(
    db: AsyncSession,
    portfolio_id: str,
    user_id: str,
    lookback_days: int = 252,
    benchmark_override: str | None = None,
    rf_override: float | None = None,
) -> RiskResponse:
    """Calculate and cache all statistical risk metrics for a portfolio."""
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

    # Resolve parameters
    benchmark_name = benchmark_override or portfolio.benchmark or BenchmarkType.SP500.value
    benchmark_ticker = BENCHMARK_TICKERS.get(benchmark_name, "^GSPC")

    # Fetch user for default risk free rate if override not provided
    rf = rf_override
    if rf is None:
        from app.models.user import User
        u_result = await db.execute(select(User).where(User.id == user_id))
        user = u_result.scalar_one_or_none()
        rf = float(user.risk_free_rate) if user else 0.05

    period = get_period_from_lookback(lookback_days)

    # 2. Fetch portfolio valuation series
    val_resp = await market_data_service.get_portfolio_valuation_series(
        db, portfolio.id, user_id, period
    )
    val_items = val_resp.valuation_series
    if not val_items or len(val_items) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio has insufficient price history for risk calculation.",
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

    # Convert to numpy arrays for calculation speed
    np_p = np.array(stat_p_returns)
    np_b = np.array(stat_b_returns)

    # 6. Perform calculations
    # Annualized returns (Geometric compounding based on values)
    val_start = sliced_values[0]
    val_end = sliced_values[-1]
    p_cum = (val_end - val_start) / val_start if val_start > 0 else 0.0
    p_ann_ret = (1.0 + p_cum) ** (252.0 / M) - 1.0 if p_cum > -1.0 else -1.0

    b_start = bench_prices[slice_start]
    b_end = bench_prices[-1]
    b_cum = (b_end - b_start) / b_start if b_start > 0 else 0.0
    b_ann_ret = (1.0 + b_cum) ** (252.0 / M) - 1.0 if b_cum > -1.0 else -1.0

    # Volatilities
    p_vol = np.std(np_p, ddof=1) * np.sqrt(252)
    b_vol = np.std(np_b, ddof=1) * np.sqrt(252)

    # Sharpe
    sharpe = (p_ann_ret - rf) / p_vol if p_vol > 0 else 0.0

    # Downside deviation & Sortino
    downside_diffs = np.minimum(np_p, 0.0)
    downside_vol = np.sqrt(np.mean(np.square(downside_diffs))) * np.sqrt(252)
    sortino = (p_ann_ret - rf) / downside_vol if downside_vol > 0 else 0.0

    # Beta
    cov = np.cov(np_p, np_b)[0][1]
    b_var = np.var(np_b, ddof=1)
    beta = cov / b_var if b_var > 0 else 0.0

    # Jensen's Alpha
    alpha = p_ann_ret - (rf + beta * (b_ann_ret - rf))

    # Tracking error & Information ratio
    excess_returns = np_p - np_b
    tracking_error = np.std(excess_returns, ddof=1) * np.sqrt(252)
    info_ratio = (p_ann_ret - b_ann_ret) / tracking_error if tracking_error > 0 else 0.0

    # Skewness & Kurtosis
    p_series = pd.Series(stat_p_returns)
    skewness = float(p_series.skew()) if not pd.isna(p_series.skew()) else 0.0
    # Pearson kurtosis (normal = 3)
    kurtosis = float(p_series.kurtosis()) + 3.0 if not pd.isna(p_series.kurtosis()) else 3.0

    # Drawdown metrics
    peak = sliced_values[0]
    peak_date = sliced_dates[0]
    valley_date = sliced_dates[0]
    max_dd = 0.0
    current_peak_date = sliced_dates[0]
    drawdowns = []

    for i, val in enumerate(sliced_values):
        if val > peak:
            peak = val
            current_peak_date = sliced_dates[i]
        dd = (val - peak) / peak if peak > 0 else 0.0
        drawdowns.append(dd)
        if dd < max_dd:
            max_dd = dd
            peak_date = current_peak_date
            valley_date = sliced_dates[i]

    current_dd = drawdowns[-1] if drawdowns else 0.0
    calmar = p_ann_ret / abs(max_dd) if max_dd and max_dd != 0 else 0.0

    # Tail metrics (Historical daily)
    var_95 = np.percentile(np_p, 5)
    var_99 = np.percentile(np_p, 1)

    cvar_95_list = np_p[np_p <= var_95]
    cvar_95 = np.mean(cvar_95_list) if len(cvar_95_list) > 0 else var_95

    cvar_99_list = np_p[np_p <= var_99]
    cvar_99 = np.mean(cvar_99_list) if len(cvar_99_list) > 0 else var_99

    # 7. Build Pydantic return structures
    metrics_details = RiskMetricsDetails(
        annualized_return=p_ann_ret,
        annualized_volatility=p_vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        beta=beta,
        alpha=alpha,
        information_ratio=info_ratio,
        tracking_error=tracking_error,
        max_drawdown=max_dd,
        max_drawdown_start=peak_date,
        max_drawdown_end=valley_date,
        current_drawdown=current_dd,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        downside_deviation=downside_vol,
        calmar_ratio=calmar,
        skewness=skewness,
        kurtosis=kurtosis,
    )

    ret_series = SeriesData(dates=sliced_dates, values=sliced_p_returns)
    dd_series = SeriesData(dates=sliced_dates, values=drawdowns)

    response = RiskResponse(
        portfolio_id=portfolio.id,
        calculation_date=datetime.now(timezone.utc),
        lookback_days=lookback_days,
        risk_free_rate=rf,
        benchmark=benchmark_name,
        metrics=metrics_details,
        return_series=ret_series,
        drawdown_series=dd_series,
    )

    # 8. Cache calculation result in database risk_metrics table
    # Delete older cached results for the same portfolio and lookback
    await db.execute(
        select(RiskMetrics)
        .where(
            and_(
                RiskMetrics.portfolio_id == portfolio.id,
                RiskMetrics.lookback_days == lookback_days,
            )
        )
    )
    # Persist new entry
    cached_db_entry = RiskMetrics(
        portfolio_id=portfolio.id,
        calculation_date=response.calculation_date,
        lookback_days=lookback_days,
        risk_free_rate=rf,
        annualized_return=p_ann_ret,
        annualized_volatility=p_vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        beta=beta,
        alpha=alpha,
        information_ratio=info_ratio,
        tracking_error=tracking_error,
        max_drawdown=max_dd,
        max_drawdown_start=datetime.strptime(peak_date, "%Y-%m-%d").date() if peak_date else None,
        max_drawdown_end=datetime.strptime(valley_date, "%Y-%m-%d").date() if valley_date else None,
        current_drawdown=current_dd,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        downside_deviation=downside_vol,
        calmar_ratio=calmar,
        skewness=skewness,
        kurtosis=kurtosis,
        benchmark=benchmark_name,
        return_series=ret_series.model_dump(),
        drawdown_series=dd_series.model_dump(),
        metadata_json={},
    )
    db.add(cached_db_entry)
    await db.flush()

    return response


async def calculate_var_details(
    db: AsyncSession,
    portfolio_id: str,
    user_id: str,
    method: str = "historical",
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> VaRResponse:
    """Calculate detailed tail risks (Value at Risk and Conditional VaR)."""
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

    portfolio_value = float(portfolio.total_value)
    if portfolio_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio value must be positive to compute VaR.",
        )

    # 2. Fetch daily returns (default 1y lookback)
    val_resp = await market_data_service.get_portfolio_valuation_series(
        db, portfolio.id, user_id, "1y"
    )
    val_items = val_resp.valuation_series
    if len(val_items) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio requires at least 5 days of history to compute VaR details.",
        )

    values = [item.value for item in val_items]
    returns = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        returns.append((curr - prev) / prev if prev > 0 else 0.0)

    np_returns = np.array(returns)
    alpha = 1.0 - confidence

    if method == "historical":
        # 1-day Historical
        var_1d = np.percentile(np_returns, alpha * 100)
        cvar_1d_list = np_returns[np_returns <= var_1d]
        cvar_1d = np.mean(cvar_1d_list) if len(cvar_1d_list) > 0 else var_1d

        # Scale by square root of horizon
        var_h = var_1d * np.sqrt(horizon_days)
        cvar_h = cvar_1d * np.sqrt(horizon_days)

    elif method == "parametric":
        # Parametric (Gaussian variance-covariance)
        mu = np.mean(np_returns)
        sigma = np.std(np_returns, ddof=1)

        # Standard normal percentiles
        # 95% = -1.644853, 99% = -2.326348
        if confidence == 0.99:
            z = -2.326348
        else:
            # Default to 95%
            z = -1.644853

        var_1d = mu + z * sigma
        phi = math.exp(-(z ** 2) / 2.0) / math.sqrt(2.0 * math.pi)
        cvar_1d = mu - sigma * (phi / alpha)

        # Scale by square root of horizon
        var_h = var_1d * np.sqrt(horizon_days)
        cvar_h = cvar_1d * np.sqrt(horizon_days)

    elif method == "monte_carlo":
        # Monte Carlo Simulation
        mu = np.mean(np_returns)
        sigma = np.std(np_returns, ddof=1)

        # Simulate 5,000 paths of returns compounded over the horizon days
        # sim_runs: size (5000, horizon_days)
        sim_runs = np.random.normal(mu, sigma, size=(5000, horizon_days))
        # Compounding: prod(1 + r) - 1
        sim_returns_h = np.prod(1.0 + sim_runs, axis=1) - 1.0

        var_h = np.percentile(sim_returns_h, alpha * 100)
        cvar_h_list = sim_returns_h[sim_returns_h <= var_h]
        cvar_h = np.mean(cvar_h_list) if len(cvar_h_list) > 0 else var_h

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown VaR method '{method}'. Supported methods: historical, parametric, monte_carlo",
        )

    # Compute absolute currency amounts
    var_amount = var_h * portfolio_value
    cvar_amount = cvar_h * portfolio_value

    # Build interpretation
    time_phrase = "a single day" if horizon_days == 1 else f"{horizon_days} trading days"
    currency_symbol = "$" if portfolio.base_currency == "USD" else f"{portfolio.base_currency} "
    interpretation = (
        f"There is a {round(alpha * 100)}% probability that the portfolio could lose "
        f"more than {currency_symbol}{abs(var_amount):,.2f} ({abs(var_h) * 100:.2f}%) in {time_phrase}."
    )

    return VaRResponse(
        method=method,
        confidence=confidence,
        horizon_days=horizon_days,
        var=var_h,
        var_amount=var_amount,
        cvar=cvar_h,
        cvar_amount=cvar_amount,
        portfolio_value=portfolio_value,
        interpretation=interpretation,
    )


async def calculate_risk_contributions(
    db: AsyncSession, portfolio_id: str, user_id: str
) -> RiskContributionsResponse:
    """Decompose portfolio risk into constituent holding contributions (Euler risk decomposition)."""
    # 1. Fetch portfolio and holdings
    result = await db.execute(
        select(Portfolio)
        .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        .options(selectinload(Portfolio.holdings))
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    holdings = portfolio.holdings
    if not holdings:
        return RiskContributionsResponse(portfolio_volatility=0.0, contributions=[])

    # 2. Fetch history for all holdings
    ticker_series = {}
    for h in holdings:
        hist = await market_data_service.get_history(db, h.ticker, "1y")
        prices_map = {
            datetime.strptime(p.date, "%Y-%m-%d").date(): p.adj_close for p in hist.prices
        }
        ticker_series[h.ticker] = prices_map

    # 3. Align holding prices using benchmark trading timeline
    benchmark_ticker = BENCHMARK_TICKERS.get(portfolio.benchmark, "^GSPC")
    bench_hist = await market_data_service.get_history(db, benchmark_ticker, "1y")
    t_dates = [datetime.strptime(p.date, "%Y-%m-%d").date() for p in bench_hist.prices]

    if not t_dates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Benchmark trading dates could not be loaded for alignment.",
        )

    # Reconstruct overlapping aligned prices
    price_df_data = {}
    for ticker, p_map in ticker_series.items():
        prices_list = []
        for d in t_dates:
            price = p_map.get(d)
            if price is None:
                # Forward fill from history map
                past_dates = [dt for dt in p_map.keys() if dt <= d]
                if past_dates:
                    price = p_map[max(past_dates)]
                else:
                    # Fallback to purchase cost basis
                    holding_obj = next(h_obj for h_obj in holdings if h_obj.ticker == ticker)
                    price = float(holding_obj.average_cost)
            prices_list.append(price)
        price_df_data[ticker] = prices_list

    # Compute daily returns matrix
    price_df = pd.DataFrame(price_df_data, index=t_dates)
    returns_df = price_df.pct_change().fillna(0.0)

    # 4. Formulate weights and covariance
    # Compute current weights of holdings in portfolio
    total_val = float(portfolio.total_value)
    if total_val > 0:
        weights = np.array([float(h.current_value) / total_val for h in holdings])
    else:
        # Fallback to equal weights
        weights = np.array([1.0 / len(holdings)] * len(holdings))

    # Normalize weights just in case
    sum_w = np.sum(weights)
    if sum_w > 0:
        w = weights / sum_w
    else:
        w = weights

    # Covariance Matrix daily
    cov_daily = returns_df.cov().values

    # Individual volatilities annualized
    indiv_vols_ann = np.sqrt(np.diag(cov_daily)) * np.sqrt(252)

    # Portfolio daily variance & volatility
    port_variance_daily = np.dot(w, np.dot(cov_daily, w))
    port_vol_daily = np.sqrt(port_variance_daily) if port_variance_daily > 0 else 0.0
    port_vol_ann = port_vol_daily * np.sqrt(252)

    # Marginal Risk Contributions (daily)
    if port_vol_daily > 0:
        marginal_contrib_daily = np.dot(cov_daily, w) / port_vol_daily
        marginal_contrib_ann = marginal_contrib_daily * np.sqrt(252)

        # Component Risk Contribution (Euler RC)
        comp_contrib = w * marginal_contrib_ann

        # Percentage Contribution (sums to 1.0, represented here as % e.g. 8.19)
        pct_contrib = (w * marginal_contrib_daily) / port_vol_daily * 100.0

        # Beta of asset to the portfolio
        beta_to_portfolio = marginal_contrib_daily / port_vol_daily
    else:
        marginal_contrib_ann = np.zeros(len(holdings))
        comp_contrib = np.zeros(len(holdings))
        pct_contrib = np.zeros(len(holdings))
        beta_to_portfolio = np.zeros(len(holdings))

    # 5. Build response list
    contributions = []
    for idx, h in enumerate(holdings):
        contributions.append(
            HoldingRiskContribution(
                ticker=h.ticker,
                weight=w[idx],
                individual_volatility=float(indiv_vols_ann[idx]),
                marginal_contribution=float(marginal_contrib_ann[idx]),
                percentage_contribution=float(pct_contrib[idx]),
                beta_to_portfolio=float(beta_to_portfolio[idx]),
            )
        )

    # Sort contributions by percentage risk contribution descending
    contributions.sort(key=lambda x: x.percentage_contribution, reverse=True)

    return RiskContributionsResponse(
        portfolio_volatility=port_vol_ann,
        contributions=contributions,
    )
