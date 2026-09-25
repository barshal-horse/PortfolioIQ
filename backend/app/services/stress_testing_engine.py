"""Stress Testing Engine — simulates historical crisis scenarios on portfolio holdings.

Implements four institutional-grade historical stress scenarios:
  1. GFC 2008 (Sep 2008 – Mar 2009)
  2. COVID-19 crash (Feb – Mar 2020)
  3. High Inflation 2022 (Jan – Oct 2022)
  4. Rate Shock 2022-23 (Mar 2022 – Jul 2023)

For each scenario the engine:
  • Fetches actual (or mocked) historical prices for every holding via market_data_service
  • Computes per-holding returns, portfolio-weighted return, max drawdown, and recovery days
  • Aggregates impacts by sector
  • Generates an executive narrative summary
  • Persists results in the stress_test_results table
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.models.stress_test_result import StressTestResult
from app.schemas.stress_test import (
    HoldingImpact,
    ScenarioInfo,
    ScenarioResult,
    SectorImpact,
    StressTestRequest,
    StressTestResponse,
    StressTestResponseData,
)
from app.services import market_data_service
from app.utils.constants import BENCHMARK_TICKERS, BenchmarkType


# ── Historical scenario definitions ─────────────────────────────────

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "gfc_2008": {
        "name": "2008 Global Financial Crisis",
        "start_date": date(2008, 9, 15),
        "end_date": date(2009, 3, 9),
        "sp500_return": -0.4689,
        "description": "Collapse of Lehman Brothers triggered a global financial meltdown.",
    },
    "covid_2020": {
        "name": "COVID-19 Market Crash",
        "start_date": date(2020, 2, 19),
        "end_date": date(2020, 3, 23),
        "sp500_return": -0.3389,
        "description": "Pandemic-driven market sell-off with the fastest bear market in history.",
    },
    "high_inflation_2022": {
        "name": "2022 Inflation Regime",
        "start_date": date(2022, 1, 3),
        "end_date": date(2022, 10, 12),
        "sp500_return": -0.2510,
        "description": "Rising inflation led to aggressive Fed rate hikes and market declines.",
    },
    "rate_shock_2022": {
        "name": "Interest Rate Shock",
        "start_date": date(2022, 3, 16),
        "end_date": date(2023, 7, 26),
        "sp500_return": -0.0820,
        "description": "Fastest Fed rate hike cycle in decades from 0.25% to 5.50%.",
    },
}


def _to_uuid(val: Any) -> uuid.UUID:
    """Safely convert string or UUID to uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


def _period_for_scenario(scenario_id: str) -> str:
    """Return a yfinance period string large enough to cover a scenario's date range."""
    s = SCENARIOS[scenario_id]
    # Compute days between start and end + generous buffer
    delta_days = (s["end_date"] - s["start_date"]).days
    if delta_days <= 60:
        return "6mo"
    elif delta_days <= 200:
        return "1y"
    elif delta_days <= 400:
        return "2y"
    else:
        return "5y"


# ── Portfolio fetching ───────────────────────────────────────────────

async def _get_portfolio_for_stress(
    db: AsyncSession, portfolio_id: Any, user_id: Any
) -> Tuple[Portfolio, List[Holding]]:
    """Fetch portfolio with holdings + instruments. Returns (portfolio, active_holdings)."""
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
    if not holdings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio has no active holdings to stress test.",
        )
    return portfolio, holdings


# ── Core scenario simulation ────────────────────────────────────────

async def _simulate_scenario(
    db: AsyncSession,
    portfolio: Portfolio,
    holdings: List[Holding],
    scenario_id: str,
) -> ScenarioResult:
    """Simulate a single historical stress scenario on the portfolio.

    For each holding:
      1. Fetch historical prices spanning the scenario window.
      2. Compute the holding's total return over the window.
      3. Compute portfolio-weighted contribution.

    Then aggregate by sector, compute portfolio-level return, max drawdown,
    estimated recovery days, and generate a narrative summary.
    """
    scenario = SCENARIOS[scenario_id]
    s_start: date = scenario["start_date"]
    s_end: date = scenario["end_date"]
    sp500_return: float = scenario["sp500_return"]
    period = _period_for_scenario(scenario_id)

    # ── 1. Compute current portfolio weights ──
    total_val = float(portfolio.total_value or 0.0)
    if total_val <= 0:
        total_val = sum(float(h.current_value or 0.0) for h in holdings)
    if total_val <= 0:
        total_val = sum(
            float(h.quantity) * float(h.current_price or h.average_cost or 1.0)
            for h in holdings
        )

    weights: Dict[str, float] = {}
    sector_map: Dict[str, str] = {}
    for h in holdings:
        h_val = float(h.current_value or 0.0)
        if h_val <= 0:
            h_val = float(h.quantity) * float(h.current_price or h.average_cost or 1.0)
        weights[h.ticker] = h_val / total_val if total_val > 0 else 1.0 / len(holdings)
        sec = h.instrument.sector if h.instrument and h.instrument.sector else "General"
        sector_map[h.ticker] = sec

    # Normalise weights
    sum_w = sum(weights.values())
    if sum_w > 0 and abs(sum_w - 1.0) > 1e-6:
        for k in weights:
            weights[k] /= sum_w

    # ── 2. Fetch prices and compute per-holding returns ──
    holding_returns: Dict[str, float] = {}
    daily_portfolio_values: List[float] = []  # for drawdown calc
    daily_holding_series: Dict[str, List[float]] = {}

    for h in holdings:
        hist = await market_data_service.get_history(db, h.ticker, period)
        # Build date→price map
        prices_map: Dict[date, float] = {}
        for p in (hist.prices or []):
            try:
                d = datetime.strptime(p.date, "%Y-%m-%d").date()
                prices_map[d] = float(p.adj_close)
            except (ValueError, TypeError):
                continue

        # Find the closest available dates within the scenario window
        available_dates = sorted(prices_map.keys())
        if not available_dates:
            # No price data — use the scenario benchmark return as proxy
            holding_returns[h.ticker] = sp500_return
            daily_holding_series[h.ticker] = []
            continue

        # Find start price — nearest date on or before scenario start
        start_candidates = [d for d in available_dates if d <= s_start]
        if start_candidates:
            start_d = max(start_candidates)
        else:
            # Fallback to first available date after scenario start
            after_start = [d for d in available_dates if d >= s_start]
            start_d = after_start[0] if after_start else available_dates[0]

        # Find end price — nearest date on or before scenario end
        end_candidates = [d for d in available_dates if d <= s_end]
        if end_candidates:
            end_d = max(end_candidates)
        else:
            end_d = available_dates[-1]

        start_price = prices_map[start_d]
        end_price = prices_map[end_d]

        if start_price > 0:
            h_return = (end_price - start_price) / start_price
        else:
            h_return = 0.0

        holding_returns[h.ticker] = round(h_return, 6)

        # Collect daily prices in scenario window for drawdown
        window_prices = [
            prices_map[d] for d in available_dates if start_d <= d <= end_d
        ]
        daily_holding_series[h.ticker] = window_prices

    # ── 3. Portfolio-level return ──
    portfolio_return = sum(
        weights.get(t, 0.0) * holding_returns.get(t, 0.0)
        for t in weights
    )

    # ── 4. Compute max drawdown from daily portfolio value series ──
    # Build a daily portfolio value index by weighting each holding's price series
    max_len = max(
        (len(s) for s in daily_holding_series.values() if s), default=0
    )
    if max_len > 1:
        portfolio_daily = np.zeros(max_len)
        for ticker, series in daily_holding_series.items():
            if not series:
                continue
            w = weights.get(ticker, 0.0)
            # Normalise series to start at 1.0
            s_arr = np.array(series, dtype=float)
            s_normalised = s_arr / s_arr[0]
            # Pad shorter series with last value
            if len(s_normalised) < max_len:
                s_normalised = np.pad(
                    s_normalised,
                    (0, max_len - len(s_normalised)),
                    mode="edge",
                )
            portfolio_daily += w * s_normalised[:max_len]

        # Drawdown calculation
        running_max = np.maximum.accumulate(portfolio_daily)
        drawdowns = (portfolio_daily - running_max) / np.where(
            running_max > 0, running_max, 1.0
        )
        max_drawdown = float(np.min(drawdowns))
    else:
        max_drawdown = portfolio_return  # single data point fallback

    # ── 5. Estimate recovery days ──
    # Simple heuristic: historical S&P 500 recovery days scaled by portfolio loss
    _recovery_heuristics = {
        "gfc_2008": 420,
        "covid_2020": 148,
        "high_inflation_2022": 280,
        "rate_shock_2022": 350,
    }
    base_recovery = _recovery_heuristics.get(scenario_id, 300)
    # Scale by ratio of portfolio loss to S&P loss (if worse, longer recovery)
    if sp500_return != 0 and portfolio_return < 0:
        ratio = abs(portfolio_return) / abs(sp500_return)
        recovery_days = int(base_recovery * ratio)
    elif portfolio_return >= 0:
        recovery_days = 0
    else:
        recovery_days = base_recovery

    # ── 6. Build per-holding impacts ──
    holding_impacts = []
    for ticker in sorted(weights.keys()):
        w = weights[ticker]
        h_ret = holding_returns.get(ticker, 0.0)
        holding_impacts.append(
            HoldingImpact(
                ticker=ticker,
                **{"return": round(h_ret, 6)},
                weight=round(w, 4),
                contribution=round(w * h_ret, 6),
            )
        )

    # ── 7. Build per-sector impacts ──
    sector_agg: Dict[str, Dict[str, float]] = {}
    for ticker, sec in sector_map.items():
        if sec not in sector_agg:
            sector_agg[sec] = {"weight": 0.0, "contrib": 0.0}
        w = weights.get(ticker, 0.0)
        h_ret = holding_returns.get(ticker, 0.0)
        sector_agg[sec]["weight"] += w
        sector_agg[sec]["contrib"] += w * h_ret

    sector_impacts = []
    for sec, data in sorted(sector_agg.items()):
        sec_weight = data["weight"]
        sec_contrib = data["contrib"]
        sec_return = sec_contrib / sec_weight if sec_weight > 0 else 0.0
        sector_impacts.append(
            SectorImpact(
                sector=sec,
                **{"return": round(sec_return, 6)},
                weight=round(sec_weight, 4),
                contribution=round(sec_contrib, 6),
            )
        )

    # ── 8. Generate narrative summary ──
    perf_verb = "declined" if portfolio_return < 0 else "gained"
    vs_bench = ""
    if portfolio_return < sp500_return:
        vs_bench = f"underperforming the S&P 500's {abs(sp500_return)*100:.2f}% decline"
    elif abs(portfolio_return - sp500_return) < 0.005:
        vs_bench = f"roughly matching the S&P 500's {abs(sp500_return)*100:.2f}% decline"
    else:
        vs_bench = f"outperforming the S&P 500's {abs(sp500_return)*100:.2f}% decline"

    worst_sector = min(sector_impacts, key=lambda s: s.contribution) if sector_impacts else None
    worst_str = (
        f" The heaviest losses would come from the {worst_sector.sector} sector."
        if worst_sector and worst_sector.contribution < 0
        else ""
    )
    recovery_str = (
        f" Recovery to pre-crisis levels would take approximately {recovery_days} trading days."
        if recovery_days and recovery_days > 0
        else " The portfolio would not require recovery as it had positive performance."
    )

    summary = (
        f"During the {scenario['name']}, this portfolio would have "
        f"{perf_verb} {abs(portfolio_return)*100:.2f}%, "
        f"{vs_bench}.{worst_str}{recovery_str}"
    )

    return ScenarioResult(
        scenario=scenario_id,
        description=f"{scenario['name']} ({s_start.strftime('%b %Y')} – {s_end.strftime('%b %Y')})",
        scenario_start=s_start.isoformat(),
        scenario_end=s_end.isoformat(),
        portfolio_return=round(portfolio_return, 6),
        max_drawdown=round(max_drawdown, 6),
        benchmark_return=sp500_return,
        recovery_days=recovery_days,
        holding_impacts=holding_impacts,
        sector_impacts=sector_impacts,
        summary=summary,
    )


# ── Public API ──────────────────────────────────────────────────────

async def run_stress_test(
    db: AsyncSession,
    portfolio_id: Any,
    user_id: Any,
    request: StressTestRequest,
) -> StressTestResponse:
    """Run one or more stress test scenarios against a portfolio.

    Persists each scenario result to the DB and returns all results.
    """
    portfolio, holdings = await _get_portfolio_for_stress(db, portfolio_id, user_id)

    # Validate requested scenarios
    for s_id in request.scenarios:
        if s_id not in SCENARIOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown stress scenario: {s_id}. "
                       f"Valid: {', '.join(SCENARIOS.keys())}",
            )

    calc_date = datetime.now(timezone.utc)
    results: List[ScenarioResult] = []

    for scenario_id in request.scenarios:
        scenario_result = await _simulate_scenario(db, portfolio, holdings, scenario_id)
        results.append(scenario_result)

        # Persist to DB
        db_result = StressTestResult(
            portfolio_id=_to_uuid(portfolio.id),
            scenario=scenario_id,
            calculation_date=calc_date,
            scenario_start_date=SCENARIOS[scenario_id]["start_date"],
            scenario_end_date=SCENARIOS[scenario_id]["end_date"],
            scenario_description=scenario_result.description,
            portfolio_return=scenario_result.portfolio_return,
            max_drawdown=scenario_result.max_drawdown,
            recovery_days=scenario_result.recovery_days,
            benchmark_return=scenario_result.benchmark_return,
            holding_impacts=[
                {
                    "ticker": h.ticker,
                    "return": h.return_,
                    "weight": h.weight,
                    "contribution": h.contribution,
                }
                for h in scenario_result.holding_impacts
            ],
            sector_impacts=[
                {
                    "sector": s.sector,
                    "return": s.return_,
                    "weight": s.weight,
                    "contribution": s.contribution,
                }
                for s in scenario_result.sector_impacts
            ],
            summary=scenario_result.summary,
        )
        db.add(db_result)

    await db.commit()

    return StressTestResponse(
        status="success",
        data=StressTestResponseData(
            portfolio_id=_to_uuid(portfolio.id),
            calculation_date=calc_date,
            scenarios=results,
        ),
    )


def get_available_scenarios() -> List[ScenarioInfo]:
    """Return metadata for all built-in stress test scenarios."""
    return [
        ScenarioInfo(
            id=s_id,
            name=s["name"],
            start_date=s["start_date"].isoformat(),
            end_date=s["end_date"].isoformat(),
            sp500_return=s["sp500_return"],
            description=s["description"],
        )
        for s_id, s in SCENARIOS.items()
    ]


async def get_stress_test_history(
    db: AsyncSession,
    portfolio_id: Any,
    user_id: Any,
    limit: int = 20,
) -> List[dict]:
    """Retrieve past stress test results for a portfolio."""
    # Verify ownership
    portfolio, _ = await _get_portfolio_for_stress(db, portfolio_id, user_id)

    result = await db.execute(
        select(StressTestResult)
        .where(StressTestResult.portfolio_id == _to_uuid(portfolio.id))
        .order_by(desc(StressTestResult.calculation_date))
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "scenario": r.scenario,
            "calculation_date": r.calculation_date.isoformat() if r.calculation_date else None,
            "portfolio_return": float(r.portfolio_return) if r.portfolio_return else None,
            "max_drawdown": float(r.max_drawdown) if r.max_drawdown else None,
            "recovery_days": r.recovery_days,
            "benchmark_return": float(r.benchmark_return) if r.benchmark_return else None,
            "summary": r.summary,
        }
        for r in rows
    ]
