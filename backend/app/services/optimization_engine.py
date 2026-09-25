"""Optimization engine service — institutional-grade portfolio optimization using PyPortfolioOpt."""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Patch scipy for pypfopt HRPOpt compatibility if newer scipy removed private attribute
import scipy.cluster.hierarchy as sch
if not hasattr(sch, "_LINKAGE_METHODS"):
    sch._LINKAGE_METHODS = (
        "single",
        "complete",
        "average",
        "weighted",
        "centroid",
        "median",
        "ward",
    )

from pypfopt import (  # noqa: E402
    BlackLittermanModel,
    EfficientFrontier,
    HRPOpt,
    expected_returns,
    objective_functions,
    risk_models,
)

from app.models.holding import Holding  # noqa: E402
from app.models.instrument import Instrument  # noqa: E402
from app.models.optimization_run import OptimizationRun  # noqa: E402
from app.models.portfolio import Portfolio  # noqa: E402
from app.schemas.optimization import (  # noqa: E402
    BlackLittermanRequest,
    BlackLittermanView,
    EfficientFrontierData,
    ExpectedMetrics,
    FrontierPosition,
    OptimizationConstraints,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationResponseData,
    TradeRecommendation,
)
from app.services import market_data_service  # noqa: E402
from app.utils.constants import BENCHMARK_TICKERS, BenchmarkType  # noqa: E402


def _get_period_from_lookback(lookback_days: int) -> str:
    """Map lookback days to yfinance history period."""
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


def _to_uuid(val: Any) -> uuid.UUID:
    """Safely convert string or UUID to uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


async def _get_portfolio_data(
    db: AsyncSession, portfolio_id: Any, user_id: Any, lookback_days: int
):
    """Fetch portfolio, holdings with instruments, and aligned historical price matrix."""
    p_uuid = _to_uuid(portfolio_id)
    u_uuid = _to_uuid(user_id)
    result = await db.execute(
        select(Portfolio)
        .where(and_(Portfolio.id == p_uuid, Portfolio.user_id == u_uuid))
        .options(selectinload(Portfolio.holdings).selectinload(Holding.instrument))
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    holdings = [h for h in portfolio.holdings if h.quantity and float(h.quantity) > 0]
    if len(holdings) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio must contain at least 2 distinct active holdings for optimization.",
        )

    period = _get_period_from_lookback(lookback_days)

    # Fetch history for all holdings
    ticker_series: Dict[str, Dict[Any, float]] = {}
    for h in holdings:
        hist = await market_data_service.get_history(db, h.ticker, period)
        if not hist.prices or len(hist.prices) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient market price history for ticker {h.ticker}.",
            )
        prices_map = {
            datetime.strptime(p.date, "%Y-%m-%d").date(): float(p.adj_close)
            for p in hist.prices
        }
        ticker_series[h.ticker] = prices_map

    # Use benchmark dates to align price trading calendar
    bench_name = portfolio.benchmark or BenchmarkType.SP500.value
    bench_ticker = BENCHMARK_TICKERS.get(bench_name, "^GSPC")
    bench_hist = await market_data_service.get_history(db, bench_ticker, period)
    t_dates = [datetime.strptime(p.date, "%Y-%m-%d").date() for p in bench_hist.prices]

    if not t_dates:
        # Fallback to union of holding dates
        all_dates = set()
        for p_map in ticker_series.values():
            all_dates.update(p_map.keys())
        t_dates = sorted(list(all_dates))

    price_df_data: Dict[str, List[float]] = {}
    for h in holdings:
        ticker = h.ticker
        p_map = ticker_series[ticker]
        prices_list = []
        for d in t_dates:
            p = p_map.get(d)
            if p is None:
                past_dates = [dt for dt in p_map.keys() if dt <= d]
                if past_dates:
                    p = p_map[max(past_dates)]
                else:
                    p = float(h.average_cost) if h.average_cost else float(h.current_price or 1.0)
            prices_list.append(p)
        price_df_data[ticker] = prices_list

    price_df = pd.DataFrame(price_df_data, index=t_dates)
    # Drop rows where any column is NaN if still remaining
    price_df = price_df.ffill().bfill()

    # Sector map
    sector_mapper: Dict[str, str] = {}
    for h in holdings:
        sec = h.instrument.sector if h.instrument and h.instrument.sector else "General"
        sector_mapper[h.ticker] = sec

    # Current weights
    total_val = float(portfolio.total_value or 0.0)
    if total_val <= 0:
        total_val = sum(float(h.current_value or 0.0) for h in holdings)
    if total_val <= 0:
        total_val = sum(
            float(h.quantity) * float(h.current_price or h.average_cost or 1.0)
            for h in holdings
        )

    current_weights: Dict[str, float] = {}
    for h in holdings:
        h_val = float(h.current_value or 0.0)
        if h_val <= 0:
            h_val = float(h.quantity) * float(h.current_price or h.average_cost or 1.0)
        current_weights[h.ticker] = h_val / total_val if total_val > 0 else 1.0 / len(holdings)

    # Normalize current weights to sum to 1.0
    sum_w = sum(current_weights.values())
    if sum_w > 0:
        for k in current_weights:
            current_weights[k] = round(current_weights[k] / sum_w, 4)

    return portfolio, holdings, price_df, sector_mapper, current_weights, total_val


def _build_trade_recommendations(
    current_weights: Dict[str, float],
    optimal_weights: Dict[str, float],
    total_val: float,
) -> List[TradeRecommendation]:
    """Generate trade rebalancing orders comparing current and optimal weights."""
    trades: List[TradeRecommendation] = []
    all_tickers = sorted(list(set(current_weights.keys()).union(set(optimal_weights.keys()))))

    for ticker in all_tickers:
        w_curr = current_weights.get(ticker, 0.0)
        w_opt = optimal_weights.get(ticker, 0.0)
        delta = round(w_opt - w_curr, 4)

        if delta > 0.002:
            action = "buy"
        elif delta < -0.002:
            action = "sell"
        else:
            action = "hold"

        est_amount = round(delta * total_val, 2)
        trades.append(
            TradeRecommendation(
                ticker=ticker,
                action=action,
                current_weight=round(w_curr, 4),
                target_weight=round(w_opt, 4),
                delta=delta,
                estimated_amount=est_amount,
            )
        )

    # Order trades: sells first to raise cash, then buys, then holds
    trades.sort(key=lambda t: (0 if t.action == "sell" else (1 if t.action == "buy" else 2), -abs(t.delta)))
    return trades


def _generate_efficient_frontier(
    mu: pd.Series,
    S: pd.DataFrame,
    bounds: tuple,
    rf: float,
    current_metrics: ExpectedMetrics,
    optimal_metrics: ExpectedMetrics,
    sector_mapper: Optional[Dict[str, str]] = None,
    sector_limits: Optional[Dict[str, float]] = None,
) -> EfficientFrontierData:
    """Generate discrete coordinates along the Markowitz Efficient Frontier curve."""
    frontier_returns: List[float] = []
    frontier_volatilities: List[float] = []
    frontier_sharpes: List[float] = []

    try:
        ef_min = EfficientFrontier(mu, S, weight_bounds=bounds)
        if sector_mapper and sector_limits:
            ef_min.add_sector_constraints(sector_mapper, sector_lower={}, sector_upper=sector_limits)
        ef_min.min_volatility()
        min_ret, min_vol, _ = ef_min.portfolio_performance(risk_free_rate=rf)

        max_asset_ret = float(mu.max())
        if max_asset_ret <= min_ret:
            max_asset_ret = min_ret + 0.10

        target_returns = np.linspace(min_ret, max_asset_ret * 0.96, 16)

        for tr in target_returns:
            try:
                ef = EfficientFrontier(mu, S, weight_bounds=bounds)
                if sector_mapper and sector_limits:
                    ef.add_sector_constraints(
                        sector_mapper, sector_lower={}, sector_upper=sector_limits
                    )
                ef.efficient_return(target_return=float(tr))
                r, v, s = ef.portfolio_performance(risk_free_rate=rf)
                frontier_returns.append(round(float(r), 4))
                frontier_volatilities.append(round(float(v), 4))
                frontier_sharpes.append(round(float(s), 4))
            except Exception:
                continue
    except Exception:
        pass

    # Ensure at least optimal position and current position exist
    if not frontier_returns:
        frontier_returns = [current_metrics.expected_return, optimal_metrics.expected_return]
        frontier_volatilities = [
            current_metrics.expected_volatility,
            optimal_metrics.expected_volatility,
        ]
        frontier_sharpes = [current_metrics.expected_sharpe, optimal_metrics.expected_sharpe]

    return EfficientFrontierData(
        returns=frontier_returns,
        volatilities=frontier_volatilities,
        sharpe_ratios=frontier_sharpes,
        current_position=FrontierPosition(
            return_=current_metrics.expected_return,
            volatility=current_metrics.expected_volatility,
        ),
        optimal_position=FrontierPosition(
            return_=optimal_metrics.expected_return,
            volatility=optimal_metrics.expected_volatility,
        ),
    )


async def run_optimization(
    db: AsyncSession,
    portfolio_id: str,
    user_id: str,
    request: OptimizationRequest,
) -> OptimizationResponse:
    """Execute standard portfolio optimization (Mean-Variance, Max Sharpe, Min Volatility, Risk Parity)."""
    (
        portfolio,
        holdings,
        price_df,
        sector_mapper,
        current_weights,
        total_val,
    ) = await _get_portfolio_data(db, portfolio_id, user_id, request.lookback_days)

    tickers = list(price_df.columns)
    n_assets = len(tickers)

    # Sanitize bounds
    c = request.constraints or OptimizationConstraints()
    min_w = float(c.min_weight)
    max_w = float(c.max_weight)

    if min_w * n_assets > 1.0:
        min_w = max(0.0, (1.0 / n_assets) * 0.5)
    if max_w * n_assets < 1.0:
        max_w = 1.0
    bounds = (min_w, max_w)

    rf = float(request.risk_free_rate)

    # Calculate returns and covariance matrix
    # Using institutional Ledoit-Wolf shrinkage covariance for numerical stability
    returns_df = price_df.pct_change().dropna()
    mu = expected_returns.capm_return(price_df, risk_free_rate=rf)
    try:
        S = risk_models.CovarianceShrinkage(price_df).ledoit_wolf()
    except Exception:
        S = risk_models.sample_cov(price_df)

    # Current metrics calculation under same mu, S
    w_curr_vec = np.array([current_weights.get(t, 0.0) for t in tickers])
    if np.sum(w_curr_vec) > 0:
        w_curr_vec = w_curr_vec / np.sum(w_curr_vec)
    else:
        w_curr_vec = np.ones(n_assets) / n_assets

    curr_exp_return = float(np.dot(w_curr_vec, mu.values))
    curr_exp_vol = float(np.sqrt(np.dot(w_curr_vec.T, np.dot(S.values, w_curr_vec))))
    curr_sharpe = float((curr_exp_return - rf) / curr_exp_vol) if curr_exp_vol > 0 else 0.0

    current_metrics = ExpectedMetrics(
        expected_return=round(curr_exp_return, 4),
        expected_volatility=round(curr_exp_vol, 4),
        expected_sharpe=round(curr_sharpe, 4),
    )

    optimal_weights: Dict[str, float] = {}
    method = request.method

    if method == "risk_parity":
        # Hierarchical Risk Parity
        try:
            hrp = HRPOpt(returns=returns_df)
            hrp.optimize()
            raw_w = hrp.clean_weights()
            optimal_weights = {k: round(float(v), 4) for k, v in raw_w.items()}
            opt_ret, opt_vol, opt_sharpe = hrp.portfolio_performance(risk_free_rate=rf)
        except Exception:
            # Fallback to inverse-volatility risk parity
            stds = np.sqrt(np.diag(S.values))
            inv_stds = 1.0 / (stds + 1e-8)
            norm_w = inv_stds / np.sum(inv_stds)
            optimal_weights = {tickers[i]: round(float(norm_w[i]), 4) for i in range(n_assets)}
            w_arr = np.array([optimal_weights[t] for t in tickers])
            opt_ret = float(np.dot(w_arr, mu.values))
            opt_vol = float(np.sqrt(np.dot(w_arr.T, np.dot(S.values, w_arr))))
            opt_sharpe = float((opt_ret - rf) / opt_vol) if opt_vol > 0 else 0.0

    else:
        ef = EfficientFrontier(mu, S, weight_bounds=bounds)

        # Apply sector constraints if provided
        if c.sector_limits:
            try:
                ef.add_sector_constraints(sector_mapper, sector_lower={}, sector_upper=c.sector_limits)
            except Exception:
                pass

        if method == "min_variance":
            ef.min_volatility()
        elif method == "mean_variance":
            # Target 1.1x current return or max_sharpe
            try:
                target_ret = max(curr_exp_return * 1.1, curr_exp_return + 0.02)
                if target_ret < float(mu.max()):
                    ef.efficient_return(target_return=target_ret)
                else:
                    ef.max_sharpe(risk_free_rate=rf)
            except Exception:
                ef.max_sharpe(risk_free_rate=rf)
        else:
            # default to max_sharpe
            try:
                ef.max_sharpe(risk_free_rate=rf)
            except Exception:
                # If solver status is infeasible, fallback to min_volatility
                ef = EfficientFrontier(mu, S, weight_bounds=(0.0, 1.0))
                ef.min_volatility()

        cleaned_w = ef.clean_weights()
        optimal_weights = {k: round(float(v), 4) for k, v in cleaned_w.items()}
        opt_ret, opt_vol, opt_sharpe = ef.portfolio_performance(risk_free_rate=rf)

    # Normalize optimal weights
    sum_opt = sum(optimal_weights.values())
    if sum_opt > 0:
        optimal_weights = {k: round(v / sum_opt, 4) for k, v in optimal_weights.items()}

    expected_metrics = ExpectedMetrics(
        expected_return=round(float(opt_ret), 4),
        expected_volatility=round(float(opt_vol), 4),
        expected_sharpe=round(float(opt_sharpe), 4),
    )

    trades = _build_trade_recommendations(current_weights, optimal_weights, total_val)

    frontier = _generate_efficient_frontier(
        mu,
        S,
        bounds,
        rf,
        current_metrics,
        expected_metrics,
        sector_mapper=sector_mapper,
        sector_limits=c.sector_limits,
    )

    # Save run to database
    run_id = uuid.uuid4()
    db_run = OptimizationRun(
        id=run_id,
        portfolio_id=portfolio.id,
        method=method,
        calculation_date=datetime.now(timezone.utc),
        constraints=c.model_dump(),
        current_weights=current_weights,
        optimal_weights=optimal_weights,
        expected_return=expected_metrics.expected_return,
        expected_volatility=expected_metrics.expected_volatility,
        expected_sharpe=expected_metrics.expected_sharpe,
        current_metrics=current_metrics.model_dump(),
        trades=[t.model_dump() for t in trades],
        efficient_frontier=frontier.model_dump(),
        views=None,
        posterior_returns=None,
        status="completed",
    )
    db.add(db_run)
    await db.commit()

    return OptimizationResponse(
        status="success",
        data=OptimizationResponseData(
            id=run_id,
            method=method,
            calculation_date=db_run.calculation_date,
            current_allocation=current_weights,
            optimal_allocation=optimal_weights,
            expected_metrics=expected_metrics,
            current_metrics=current_metrics,
            trades=trades,
            efficient_frontier=frontier,
        ),
    )


async def run_black_litterman_optimization(
    db: AsyncSession,
    portfolio_id: str,
    user_id: str,
    request: BlackLittermanRequest,
) -> OptimizationResponse:
    """Execute Black-Litterman portfolio optimization incorporating subjective views."""
    (
        portfolio,
        holdings,
        price_df,
        sector_mapper,
        current_weights,
        total_val,
    ) = await _get_portfolio_data(db, portfolio_id, user_id, request.lookback_days)

    tickers = list(price_df.columns)
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}
    n_assets = len(tickers)

    rf = float(request.risk_free_rate)
    c = request.constraints or OptimizationConstraints()
    min_w = float(c.min_weight)
    max_w = float(c.max_weight)
    if min_w * n_assets > 1.0:
        min_w = 0.0
    if max_w * n_assets < 1.0:
        max_w = 1.0
    bounds = (min_w, max_w)

    try:
        S = risk_models.CovarianceShrinkage(price_df).ledoit_wolf()
    except Exception:
        S = risk_models.sample_cov(price_df)

    market_prior = expected_returns.capm_return(price_df, risk_free_rate=rf)

    # Current metrics
    w_curr_vec = np.array([current_weights.get(t, 0.0) for t in tickers])
    if np.sum(w_curr_vec) > 0:
        w_curr_vec = w_curr_vec / np.sum(w_curr_vec)
    else:
        w_curr_vec = np.ones(n_assets) / n_assets

    curr_exp_return = float(np.dot(w_curr_vec, market_prior.values))
    curr_exp_vol = float(np.sqrt(np.dot(w_curr_vec.T, np.dot(S.values, w_curr_vec))))
    curr_sharpe = float((curr_exp_return - rf) / curr_exp_vol) if curr_exp_vol > 0 else 0.0

    current_metrics = ExpectedMetrics(
        expected_return=round(curr_exp_return, 4),
        expected_volatility=round(curr_exp_vol, 4),
        expected_sharpe=round(curr_sharpe, 4),
    )

    # Build P, Q, and omega matrices from views
    p_rows = []
    q_vals = []
    conf_diags = []

    for v in request.views:
        p_row = np.zeros(n_assets)
        if v.type == "absolute":
            if not v.ticker or v.ticker not in ticker_to_idx:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ticker '{v.ticker}' in view not found in portfolio holdings: {tickers}",
                )
            if v.expected_return is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Absolute view on '{v.ticker}' missing 'expected_return'.",
                )
            p_row[ticker_to_idx[v.ticker]] = 1.0
            q_vals.append(float(v.expected_return))

        elif v.type == "relative":
            if not v.long_ticker or v.long_ticker not in ticker_to_idx:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Long ticker '{v.long_ticker}' in relative view not in portfolio holdings: {tickers}",
                )
            if not v.short_ticker or v.short_ticker not in ticker_to_idx:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Short ticker '{v.short_ticker}' in relative view not in portfolio holdings: {tickers}",
                )
            if v.expected_outperformance is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Relative view missing 'expected_outperformance'.",
                )
            p_row[ticker_to_idx[v.long_ticker]] = 1.0
            p_row[ticker_to_idx[v.short_ticker]] = -1.0
            q_vals.append(float(v.expected_outperformance))

        p_rows.append(p_row)
        # Confidence determines omega: higher confidence = smaller variance
        conf = float(v.confidence)
        conf_variance = ((1.0 - conf) / (conf + 1e-4)) * 0.05 + 0.001
        conf_diags.append(conf_variance)

    P = np.array(p_rows)
    Q = np.array(q_vals)
    omega = np.diag(conf_diags)

    bl = BlackLittermanModel(S, pi=market_prior, P=P, Q=Q, omega=omega, tau=0.05)
    posterior_rets = bl.bl_returns()
    posterior_cov = bl.bl_cov()

    ef = EfficientFrontier(posterior_rets, posterior_cov, weight_bounds=bounds)
    if c.sector_limits:
        try:
            ef.add_sector_constraints(sector_mapper, sector_lower={}, sector_upper=c.sector_limits)
        except Exception:
            pass

    try:
        ef.max_sharpe(risk_free_rate=rf)
    except Exception:
        ef = EfficientFrontier(posterior_rets, posterior_cov, weight_bounds=(0.0, 1.0))
        ef.min_volatility()

    raw_w = ef.clean_weights()
    optimal_weights = {k: round(float(v), 4) for k, v in raw_w.items()}
    sum_opt = sum(optimal_weights.values())
    if sum_opt > 0:
        optimal_weights = {k: round(v / sum_opt, 4) for k, v in optimal_weights.items()}

    opt_ret, opt_vol, opt_sharpe = ef.portfolio_performance(risk_free_rate=rf)

    expected_metrics = ExpectedMetrics(
        expected_return=round(float(opt_ret), 4),
        expected_volatility=round(float(opt_vol), 4),
        expected_sharpe=round(float(opt_sharpe), 4),
    )

    trades = _build_trade_recommendations(current_weights, optimal_weights, total_val)

    frontier = _generate_efficient_frontier(
        posterior_rets,
        posterior_cov,
        bounds,
        rf,
        current_metrics,
        expected_metrics,
        sector_mapper=sector_mapper,
        sector_limits=c.sector_limits,
    )

    posterior_dict = {k: round(float(v), 4) for k, v in posterior_rets.items()}

    # Save to database
    run_id = uuid.uuid4()
    db_run = OptimizationRun(
        id=run_id,
        portfolio_id=portfolio.id,
        method="black_litterman",
        calculation_date=datetime.now(timezone.utc),
        constraints=c.model_dump(),
        current_weights=current_weights,
        optimal_weights=optimal_weights,
        expected_return=expected_metrics.expected_return,
        expected_volatility=expected_metrics.expected_volatility,
        expected_sharpe=expected_metrics.expected_sharpe,
        current_metrics=current_metrics.model_dump(),
        trades=[t.model_dump() for t in trades],
        efficient_frontier=frontier.model_dump(),
        views=[v.model_dump() for v in request.views],
        posterior_returns=posterior_dict,
        status="completed",
    )
    db.add(db_run)
    await db.commit()

    return OptimizationResponse(
        status="success",
        data=OptimizationResponseData(
            id=run_id,
            method="black_litterman",
            calculation_date=db_run.calculation_date,
            current_allocation=current_weights,
            optimal_allocation=optimal_weights,
            expected_metrics=expected_metrics,
            current_metrics=current_metrics,
            trades=trades,
            efficient_frontier=frontier,
            views=[v.model_dump() for v in request.views],
            posterior_returns=posterior_dict,
        ),
    )


async def get_optimization_history(
    db: AsyncSession,
    portfolio_id: Any,
    user_id: Any,
    limit: int = 10,
) -> List[OptimizationResponseData]:
    """Retrieve past optimization run records for a portfolio."""
    p_uuid = _to_uuid(portfolio_id)
    u_uuid = _to_uuid(user_id)
    # Verify portfolio ownership
    p_res = await db.execute(
        select(Portfolio.id).where(
            and_(Portfolio.id == p_uuid, Portfolio.user_id == u_uuid)
        )
    )
    if not p_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    res = await db.execute(
        select(OptimizationRun)
        .where(OptimizationRun.portfolio_id == p_uuid)
        .order_by(desc(OptimizationRun.calculation_date))
        .limit(limit)
    )
    runs = res.scalars().all()

    output = []
    for r in runs:
        output.append(
            OptimizationResponseData(
                id=r.id,
                method=r.method,
                calculation_date=r.calculation_date,
                current_allocation=r.current_weights or {},
                optimal_allocation=r.optimal_weights or {},
                expected_metrics=ExpectedMetrics(
                    expected_return=float(r.expected_return or 0.0),
                    expected_volatility=float(r.expected_volatility or 0.0),
                    expected_sharpe=float(r.expected_sharpe or 0.0),
                ),
                current_metrics=ExpectedMetrics(
                    expected_return=float(r.current_metrics.get("expected_return", 0.0)),
                    expected_volatility=float(r.current_metrics.get("expected_volatility", 0.0)),
                    expected_sharpe=float(r.current_metrics.get("expected_sharpe", 0.0)),
                )
                if r.current_metrics
                else None,
                trades=[TradeRecommendation(**t) for t in (r.trades or [])],
                efficient_frontier=EfficientFrontierData(**r.efficient_frontier)
                if r.efficient_frontier
                else None,
                views=r.views,
                posterior_returns=r.posterior_returns,
            )
        )
    return output
