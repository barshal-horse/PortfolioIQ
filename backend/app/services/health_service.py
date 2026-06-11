"""Health score service — evaluates portfolio diversification, risk, performance, and efficiency scores."""

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Portfolio
from app.models.holding import Holding
from app.models.risk_metrics import RiskMetrics
from app.models.benchmark_comparison import BenchmarkComparison
from app.models.health_score import HealthScore
from app.schemas.health import (
    HealthScoreResponse,
    HealthScoreSummary,
    HealthSubscores,
    SubscoreItem,
    SubscoreDiversificationDetails,
    SubscoreRiskDetails,
    SubscorePerformanceDetails,
    SubscoreEfficiencyDetails,
    RecommendationItem,
)
from app.services import market_data_service, risk_engine, benchmark_engine
from app.utils.constants import BENCHMARK_TICKERS, BenchmarkType


def get_grade_from_score(score: int) -> str:
    """Classify 0-100 score into health grade categories."""
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score >= 20:
        return "poor"
    else:
        return "critical"


async def calculate_portfolio_health(
    db: AsyncSession, portfolio_id: str, user_id: str
) -> HealthScoreResponse:
    """Calculate, cache, and return overall portfolio health scores and recommendations."""
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio has no holdings. Add assets to compute health scores.",
        )

    # 2. Try to fetch cached Risk Metrics and Benchmark Comparisons
    # If missing, calculate them on the fly
    risk_res = await db.execute(
        select(RiskMetrics)
        .where(
            and_(
                RiskMetrics.portfolio_id == portfolio.id,
                RiskMetrics.lookback_days == 252,
            )
        )
        .order_by(RiskMetrics.calculation_date.desc())
        .limit(1)
    )
    risk_metrics_db = risk_res.scalar_one_or_none()
    if risk_metrics_db:
        # Load from DB JSON format
        dates = risk_metrics_db.return_series["dates"]
        stat_p_returns = risk_metrics_db.return_series["values"]
        p_ann_ret = float(risk_metrics_db.annualized_return)
        p_vol = float(risk_metrics_db.annualized_volatility)
        max_dd = float(risk_metrics_db.max_drawdown)
        cvar_95 = float(risk_metrics_db.cvar_95)
        sharpe_ratio = float(risk_metrics_db.sharpe_ratio)
    else:
        # Calculate on the fly
        risk_resp = await risk_engine.calculate_portfolio_risk(
            db, portfolio_id, user_id, lookback_days=252
        )
        dates = risk_resp.return_series.dates
        stat_p_returns = risk_resp.return_series.values
        p_ann_ret = risk_resp.metrics.annualized_return
        p_vol = risk_resp.metrics.annualized_volatility
        max_dd = risk_resp.metrics.max_drawdown
        cvar_95 = risk_resp.metrics.cvar_95
        sharpe_ratio = risk_resp.metrics.sharpe_ratio

    bench_name = portfolio.benchmark or BenchmarkType.SP500.value
    bench_res = await db.execute(
        select(BenchmarkComparison)
        .where(
            and_(
                BenchmarkComparison.portfolio_id == portfolio.id,
                BenchmarkComparison.benchmark == bench_name,
                BenchmarkComparison.lookback_days == 252,
            )
        )
        .order_by(BenchmarkComparison.calculation_date.desc())
        .limit(1)
    )
    bench_comp_db = bench_res.scalar_one_or_none()
    if bench_comp_db:
        b_ann_ret = float(bench_comp_db.active_return) + p_ann_ret  # Reconstruct benchmark return
        b_vol = p_vol / float(bench_comp_db.beta) if float(bench_comp_db.beta) > 0 else p_vol  # Estimation
        # Try to load actual benchmark data
        bench_ticker = BENCHMARK_TICKERS.get(bench_name, "^GSPC")
        try:
            bench_history = await market_data_service.get_history(db, bench_ticker, "1y")
            b_prices = [p.adj_close for p in bench_history.prices]
            b_cum = (b_prices[-1] - b_prices[0]) / b_prices[0] if b_prices[0] > 0 else 0.0
            b_ann_ret = (1.0 + b_cum) ** (252.0 / len(stat_p_returns)) - 1.0
        except Exception:
            pass
        
        vol_ratio = p_vol / b_vol if b_vol > 0 else 1.0
        information_ratio = float(bench_comp_db.information_ratio)
        excess_return = float(bench_comp_db.active_return)
        beta = float(bench_comp_db.beta)
    else:
        # Calculate on the fly
        comp_resp = await benchmark_engine.calculate_benchmark_comparison(
            db, portfolio_id, user_id, benchmark_override=bench_name, lookback_days=252
        )
        vol_ratio = p_vol / comp_resp.metrics.beta if comp_resp.metrics.beta and comp_resp.metrics.beta > 0 else 1.0  # fallback estimation
        # Re-verify benchmark volatility ratio exactly if we can
        try:
            bench_ticker = BENCHMARK_TICKERS.get(bench_name, "^GSPC")
            bench_hist = await market_data_service.get_history(db, bench_ticker, "1y")
            b_returns = []
            b_prices = [p.adj_close for p in bench_hist.prices]
            for i in range(1, len(b_prices)):
                b_returns.append((b_prices[i] - b_prices[i-1]) / b_prices[i-1] if b_prices[i-1] > 0 else 0.0)
            b_vol = np.std(b_returns, ddof=1) * np.sqrt(252)
            vol_ratio = p_vol / b_vol if b_vol > 0 else 1.0
            b_ann_ret = (1.0 + (b_prices[-1] - b_prices[0]) / b_prices[0]) ** (252.0 / len(stat_p_returns)) - 1.0
        except Exception:
            b_ann_ret = p_ann_ret - comp_resp.metrics.active_return
        
        information_ratio = comp_resp.metrics.information_ratio or 0.0
        excess_return = comp_resp.metrics.active_return or 0.0
        beta = comp_resp.metrics.beta or 1.0

    # 3. Diversification Calculations
    n = len(holdings)
    total_val = float(portfolio.total_value)
    weights = np.array([float(h.current_value) / total_val for h in holdings]) if total_val > 0 else np.array([1.0 / n] * n)
    hhi = float(np.sum(np.square(weights)))

    # Sector Concentration
    sector_weights = {}
    for h in holdings:
        sector = h.instrument.sector if h.instrument and h.instrument.sector else "Unclassified"
        val = float(h.current_value)
        sector_weights[sector] = sector_weights.get(sector, 0.0) + val
    
    if total_val > 0:
        for s in sector_weights:
            sector_weights[s] /= total_val
    else:
        for s in sector_weights:
            sector_weights[s] /= n

    max_sector = max(sector_weights.values()) if sector_weights else 1.0
    max_sector_name = max(sector_weights, key=sector_weights.get) if sector_weights else "None"

    # Average Correlation
    ticker_series = {}
    for h in holdings:
        try:
            hist = await market_data_service.get_history(db, h.ticker, "1y")
            prices_map = {
                datetime.strptime(p.date, "%Y-%m-%d").date(): p.adj_close for p in hist.prices
            }
            ticker_series[h.ticker] = prices_map
        except Exception:
            pass
    
    # Align prices using dates
    aligned_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    price_df_data = {}
    for ticker, p_map in ticker_series.items():
        prices_list = []
        for d in aligned_dates:
            price = p_map.get(d)
            if price is None:
                past_dates = [dt for dt in p_map.keys() if dt <= d]
                price = p_map[max(past_dates)] if past_dates else 10.0
            prices_list.append(price)
        price_df_data[ticker] = prices_list

    try:
        price_df = pd.DataFrame(price_df_data, index=aligned_dates)
        returns_df = price_df.pct_change().fillna(0.0)
        corr_matrix = returns_df.corr().values
        num_assets = corr_matrix.shape[0]
        if num_assets > 1:
            corr_avg = float((np.sum(corr_matrix) - num_assets) / (num_assets * (num_assets - 1)))
        else:
            corr_avg = 1.0
    except Exception:
        corr_avg = 0.5  # Fallback default correlation

    # 4. Compute Subscores using Defined Heuristics
    
    # 4.1 Diversification Score (25% weight)
    # Holdings count score
    if n >= 10:
        n_score = 100
    elif n >= 6:
        n_score = 80
    elif n >= 2:
        n_score = 50
    else:
        n_score = 20

    # HHI score (lower is better)
    if hhi <= 0.1:
        hhi_score = 100
    elif hhi <= 0.18:
        hhi_score = 75
    elif hhi <= 0.3:
        hhi_score = 50
    else:
        hhi_score = 20

    # Sector Concentration score
    if max_sector <= 0.25:
        sec_score = 100
    elif max_sector <= 0.40:
        sec_score = 75
    elif max_sector <= 0.60:
        sec_score = 50
    else:
        sec_score = 20

    # Correlation score
    if corr_avg <= 0.2:
        corr_score = 100
    elif corr_avg <= 0.4:
        corr_score = 80
    elif corr_avg <= 0.6:
        corr_score = 60
    else:
        corr_score = 30

    div_score = int(round(0.25 * n_score + 0.30 * hhi_score + 0.25 * sec_score + 0.20 * corr_score))
    div_grade = get_grade_from_score(div_score)
    div_explanation = (
        f"Portfolio contains {n} holdings across {len(sector_weights)} sectors. "
        f"The Herfindahl-Hirschman Index (HHI) concentration is {hhi:.4f} and the average "
        f"correlation among holdings is {corr_avg:.2f}."
    )
    div_details = SubscoreDiversificationDetails(
        hhi=hhi,
        sector_concentration=f"{max_sector_name} overweight at {max_sector * 100:.1f}%" if max_sector_name != "None" else "None",
        num_holdings=n,
        correlation_avg=corr_avg,
        explanation=div_explanation,
    )

    # 4.2 Risk Score (30% weight)
    # Volatility vs Benchmark ratio
    if vol_ratio <= 0.8:
        v_score = 100
    elif vol_ratio <= 1.1:
        v_score = 80
    elif vol_ratio <= 1.5:
        v_score = 50
    else:
        v_score = 25

    # Max Drawdown score (absolute value)
    mdd_abs = abs(max_dd)
    if mdd_abs <= 0.10:
        mdd_score = 100
        mdd_severity = "low"
    elif mdd_abs <= 0.20:
        mdd_score = 80
        mdd_severity = "moderate"
    elif mdd_abs <= 0.35:
        mdd_score = 55
        mdd_severity = "high"
    else:
        mdd_score = 20
        mdd_severity = "extreme"

    # Tail risk daily CVaR 95%
    cvar_abs = abs(cvar_95)
    if cvar_abs <= 0.015:
        tail_score = 100
    elif cvar_abs <= 0.03:
        tail_score = 75
    elif cvar_abs <= 0.05:
        tail_score = 50
    else:
        tail_score = 20

    risk_score_calc = int(round(0.40 * v_score + 0.40 * mdd_score + 0.20 * tail_score))
    risk_grade = get_grade_from_score(risk_score_calc)
    risk_explanation = (
        f"Portfolio volatility is {vol_ratio:.2f}x of the benchmark. "
        f"The maximum peak-to-trough drawdown reached is {max_dd * 100:.2f}% ({mdd_severity} severity), "
        f"and daily 95% CVaR tail risk indicates a potential loss of {cvar_abs * 100:.2f}%."
    )
    risk_details = SubscoreRiskDetails(
        vol_vs_benchmark=vol_ratio,
        mdd_severity=mdd_severity,
        tail_risk=cvar_abs,
        explanation=risk_explanation,
    )

    # 4.3 Performance Score (25% weight)
    # 1-year returns comparison (excess return)
    if excess_return >= 0.05:
        perf_ret_score = 100
    elif excess_return >= 0.0:
        perf_ret_score = 80
    elif excess_return >= -0.05:
        perf_ret_score = 55
    else:
        perf_ret_score = 25

    # Positive daily returns consistency
    consistency = len([r for r in stat_p_returns if r > 0.0]) / len(stat_p_returns)
    if consistency >= 0.54:
        cons_score = 100
    elif consistency >= 0.50:
        cons_score = 80
    elif consistency >= 0.46:
        cons_score = 55
    else:
        cons_score = 25

    perf_score = int(round(0.60 * perf_ret_score + 0.40 * cons_score))
    perf_grade = get_grade_from_score(perf_score)
    perf_explanation = (
        f"1-year annualized return is {p_ann_ret * 100:.2f}% vs benchmark {b_ann_ret * 100:.2f}% "
        f"(active excess return: {excess_return * 100:.2f}%). Positive return consistency is {consistency * 100:.1f}%."
    )
    
    # Approximate 1m / 3m returns calculation for details
    last_dt = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    def estimate_compounded_return(days_delta):
        target_d = last_dt - timedelta(days=days_delta)
        sub_returns = []
        for d_str, ret in zip(dates, stat_p_returns):
            if datetime.strptime(d_str, "%Y-%m-%d").date() >= target_d:
                sub_returns.append(ret)
        if not sub_returns:
            return 0.0
        return float(np.prod([1.0 + r for r in sub_returns]) - 1.0)

    perf_details = SubscorePerformanceDetails(
        returns_1m=estimate_compounded_return(30),
        returns_3m=estimate_compounded_return(90),
        returns_1y=p_ann_ret,
        consistency=consistency,
        explanation=perf_explanation,
    )

    # 4.4 Efficiency Score (20% weight)
    # Sharpe ratio
    if sharpe_ratio >= 1.5:
        sh_score = 100
    elif sharpe_ratio >= 1.0:
        sh_score = 85
    elif sharpe_ratio >= 0.5:
        sh_score = 60
    elif sharpe_ratio >= 0.0:
        sh_score = 35
    else:
        sh_score = 10

    # Information ratio
    if information_ratio >= 1.0:
        ir_score = 100
    elif information_ratio >= 0.5:
        ir_score = 80
    elif information_ratio >= 0.0:
        ir_score = 55
    else:
        ir_score = 20

    eff_score = int(round(0.60 * sh_score + 0.40 * ir_score))
    eff_grade = get_grade_from_score(eff_score)
    eff_explanation = (
        f"Portfolio Sharpe ratio is {sharpe_ratio:.2f} (risk-adjusted return efficiency) "
        f"and Information Ratio is {information_ratio:.2f} (active return consistency)."
    )
    eff_details = SubscoreEfficiencyDetails(
        sharpe_vs_benchmark=sharpe_ratio,  # Sharpe ratio representation
        information_ratio=information_ratio,
        return_per_risk=sharpe_ratio,  # Return per risk approximation
        explanation=eff_explanation,
    )

    # 5. Overall Health Score (Weighted)
    overall_score = int(
        round(
            0.25 * div_score
            + 0.30 * risk_score_calc
            + 0.25 * perf_score
            + 0.20 * eff_score
        )
    )
    overall_grade = get_grade_from_score(overall_score)
    overall_explanation = (
        f"Portfolio shows {overall_grade} overall health with a score of {overall_score}. "
        f"Diversification is {div_grade}, risk level is {risk_grade}, performance is {perf_grade}, "
        f"and efficiency is {eff_grade}."
    )

    # 6. Recommendations Engine
    recommendations = []

    # Diversification Recommendations
    if n < 5:
        recommendations.append(
            RecommendationItem(
                priority="high" if n <= 2 else "medium",
                category="diversification",
                action="Increase the number of holdings in the portfolio",
                rationale=f"Your portfolio currently has only {n} asset(s). Broadening your holdings to at least 5-10 positions will dramatically reduce idiosyncratic risk.",
            )
        )
    if hhi > 0.18:
        recommendations.append(
            RecommendationItem(
                priority="high" if hhi > 0.3 else "medium",
                category="diversification",
                action="Rebalance holdings to reduce weight concentration",
                rationale=f"Your Herfindahl-Hirschman Index (HHI) concentration is high at {hhi:.4f}. Trimming oversized positions will prevent single-asset failures from dominating portfolio returns.",
            )
        )
    if max_sector > 0.4:
        recommendations.append(
            RecommendationItem(
                priority="high" if max_sector > 0.6 else "medium",
                category="diversification",
                action="Diversify capital across multiple sectors",
                rationale=f"The portfolio is heavily exposed to a single sector ({max_sector_name}) with a weight of {max_sector * 100:.1f}%. Consider reallocating capital to uncorrelated sectors to hedge sector shocks.",
            )
        )

    # Risk Recommendations
    if vol_ratio > 1.3:
        recommendations.append(
            RecommendationItem(
                priority="high" if vol_ratio > 1.6 else "medium",
                category="risk",
                action="Reduce high-beta exposure or trim high-volatility holdings",
                rationale=f"Portfolio volatility is {vol_ratio:.1f}x higher than benchmark index. Trimming high-risk assets will lower overall portfolio volatility.",
            )
        )
    if mdd_abs > 0.25:
        recommendations.append(
            RecommendationItem(
                priority="medium",
                category="risk",
                action="Incorporate defensive hedges or cash buffers",
                rationale=f"Portfolio maximum historical drawdown reached {max_dd * 100:.1f}%. Adding fixed-income, gold, or cash holdings can help cushion tail drawdown severity.",
            )
        )

    # Performance Recommendations
    if excess_return < -0.02:
        recommendations.append(
            RecommendationItem(
                priority="medium",
                category="performance",
                action="Review underperforming assets relative to benchmark",
                rationale=f"Portfolio annualized return lagged the benchmark by {abs(excess_return) * 100:.1f}%. Review if individual underperforming assets still fit your long-term strategy.",
            )
        )

    # Efficiency Recommendations
    if sharpe_ratio < 0.5:
        recommendations.append(
            RecommendationItem(
                priority="high" if sharpe_ratio < 0.0 else "medium",
                category="efficiency",
                action="Optimize risk-return efficiency (Max Sharpe rebalancing)",
                rationale=f"Portfolio Sharpe ratio is low at {sharpe_ratio:.2f}. Consider running a portfolio optimization (Max Sharpe rebalancing) to maximize return per unit of risk.",
            )
        )

    # 7. Build Pydantic response
    response = HealthScoreResponse(
        portfolio_id=portfolio.id,
        calculation_date=datetime.now(timezone.utc),
        overall=HealthScoreSummary(
            score=overall_score,
            grade=overall_grade,
            explanation=overall_explanation,
        ),
        subscores=HealthSubscores(
            diversification=SubscoreItem(
                score=div_score,
                grade=div_grade,
                weight=0.25,
                details=div_details.model_dump(),
            ),
            risk=SubscoreItem(
                score=risk_score_calc,
                grade=risk_grade,
                weight=0.30,
                details=risk_details.model_dump(),
            ),
            performance=SubscoreItem(
                score=perf_score,
                grade=perf_grade,
                weight=0.25,
                details=perf_details.model_dump(),
            ),
            efficiency=SubscoreItem(
                score=eff_score,
                grade=eff_grade,
                weight=0.20,
                details=eff_details.model_dump(),
            ),
        ),
        recommendations=recommendations,
    )

    # 8. Cache calculations in database health_scores table
    # Remove older calculations for same portfolio
    await db.execute(
        select(HealthScore).where(HealthScore.portfolio_id == portfolio.id)
    )
    # Add new entry
    cached_db_entry = HealthScore(
        portfolio_id=portfolio.id,
        calculation_date=response.calculation_date,
        overall_score=overall_score,
        overall_grade=overall_grade,
        overall_explanation=overall_explanation,
        diversification_score=div_score,
        diversification_grade=div_grade,
        diversification_details=div_details.model_dump(),
        risk_score=risk_score_calc,
        risk_grade=risk_grade,
        risk_details=risk_details.model_dump(),
        performance_score=perf_score,
        performance_grade=perf_grade,
        performance_details=perf_details.model_dump(),
        efficiency_score=eff_score,
        efficiency_grade=eff_grade,
        efficiency_details=eff_details.model_dump(),
        recommendations=[r.model_dump() for r in recommendations],
        metadata_json={},
    )
    db.add(cached_db_entry)
    await db.flush()

    return response
