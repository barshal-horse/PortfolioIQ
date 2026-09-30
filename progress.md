# PortfolioIQ — Progress Tracker

> Last updated: 2026-09-30

---

## Remediation & Completion Round (2026-09-30) ✅

**Status**: Complete

A full audit found that Phases 10–12 were broken at runtime despite being marked complete.
All issues were fixed and verified with a 25-check end-to-end API smoke test (ALL PASS)
and the 74-test backend suite (74 passed).

### Runtime bugs fixed
- Reporting engine: removed invalid `await` on sync `_build_report` — **no PDF could ever generate before**
- Copilot tools: fixed 5 calls to non-existent service functions (real names wired: `calculate_risk_contributions`, `calculate_portfolio_health`, `run_optimization`, `get_portfolio_returns_series`, `calculate_benchmark_comparison`)
- Copilot router: LLM could route to 6 phantom agents not in the graph → registry now matches the actual LangGraph
- Copilot streaming: was hardcoding a placeholder `user_id` and dropping `portfolio_id` — real context now flows through
- News scheduler: missing `select`/`NewsArticle` imports (2 of 3 jobs crashed) and was never started — now started in app lifespan (disable with `DISABLE_NEWS_SCHEDULER=true`)
- News refresh API: passed `db` as `portfolio_id` — signature mismatch crash
- Sentiment `analyze_batch`: fixed self-appending infinite loop; Gemini calls moved off the event loop via `asyncio.to_thread`
- Env plumbing: API keys in `.env` were invisible to `os.getenv()` reads — all AI/news keys now load via pydantic settings
- Cross-cutting: `str`→`uuid.UUID` coercion at all service entry points (`app/utils/ids.py`) — fixed 500s on risk/benchmark/health/news on the live server
- `health_service`: eager-load `Holding.instrument` (async lazy-load crash)
- `market_data_service`: missing `timedelta` import broke both the DB cache path and FX fallback path
- `HistoryPriceItem`: added `from_attributes` + date coercion (DB `Date` objects failed validation)
- `Report` model: added missing `created_at` column mapping (API referenced it in 3 places)
- CORS: any-port localhost dev origins via `allow_origin_regex`, extras via `CORS_EXTRA_ORIGINS`

### New features (2026-09-30)
- **Simplified signup**: only email + password (name derived from email server-side)
- **Google sign-in**: Firebase Auth — `/auth/google` endpoint verifies Firebase ID tokens against Google JWKS; frontend lazy-loads the Firebase SDK. Configure with `FIREBASE_PROJECT_ID` (backend) + `NEXT_PUBLIC_FIREBASE_*` (frontend). Button shows disabled state until configured.
- **Ticker autocomplete**: `/market-data/search` endpoint (Yahoo Finance) powering a debounced suggestion dropdown in the Add Holding modal; picking a ticker auto-fetches the live price and pre-fills avg cost
- **Alpaca broker sync**: connect/disconnect per-user API keys (`broker_connections` table, migration `4a4eb302255b`), live position fetch, one-click sync into any portfolio (merge/replace). UI card on the Overview tab.
- **Frontend UIs built for Phases 10–12** (previously backend-only): Copilot sidebar with SSE streaming + citations, News Intelligence tab (feed + sentiment cards + refresh), Reports tab (generate/poll/download/delete)
- **Optimization + Stress Testing nav buttons added** — Phase 8/9 dashboards existed but were unreachable before
- **OptimizationPanel component**: method selector, weight-constraint sliders, expected metrics, rebalancing trades table

### Known follow-ups
- Angel One SmartAPI integration (user requested for later; Alpaca shipped first)
- Firebase project setup is a manual user step (create project → set env vars)
- `reports` table's `updated_at`/index drift between migration and model is cosmetic
- Rate-limit middleware (slowapi) still not wired; scheduled for hardening round

---

---

## Phase 1 — Architecture & Design Documents ✅

**Status**: Complete  
**Date**: 2026-06-12

Deliverables:
- [x] `docs/ARCHITECTURE.md` — System architecture, tech stack, 10 services, data flows, directory structure
- [x] `docs/DATABASE_SCHEMA.md` — 14 tables, 12 enums, 20+ indexes, 5 triggers, migration strategy
- [x] `docs/API_SPECIFICATION.md` — 50+ endpoints, full request/response schemas, rate limits
- [x] `docs/LANGGRAPH_ARCHITECTURE.md` — 12 agents, 28 tools, state machine, Gemini config, guardrails
- [x] `docs/MASTER_BUILD_PLAN.md` — Updated with phase roadmap

Key decisions:
- Multi-user JWT auth from Phase 2
- Multi-currency support (USD default)
- No Redis/Celery — using TTLCache + APScheduler
- Supervisor-worker agent architecture

---

## Phase 2 — Portfolio Upload (CSV & Manual Holdings) ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Backend project scaffolding (FastAPI + pyproject.toml)
- [x] Database models (SQLAlchemy 2.0 async)
  - [x] User model
  - [x] Portfolio model
  - [x] Instrument model
  - [x] Holding model
  - [x] Transaction model
- [x] Alembic migration setup and initial migration script
- [x] Pydantic schemas (request/response)
- [x] Services
  - [x] Auth service (JWT + direct bcrypt)
  - [x] Portfolio service (CRUD)
  - [x] CSV parser + validator
- [x] API endpoints
  - [x] Auth (register, login, refresh, me)
  - [x] Portfolios (CRUD)
  - [x] Holdings (add, update, delete, bulk)
  - [x] CSV upload
- [x] Unit tests (40 tests passing)
- [x] Docker Compose (PostgreSQL) and .env.example

---

## Phase 3 — Market Data Service ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Database models (PriceHistory, Dividend, Split, ExchangeRate, CacheEntry)
- [x] Pydantic schemas (Quote, History, Valuation, Returns, Benchmarks)
- [x] Cache service (2-tier: In-Memory + DB Caching with TTL)
- [x] Core Market Data Service (yfinance integration, quote fetching, historical prices, daily returns, exchange rate fallbacks, portfolio valuation series, daily returns series)
- [x] API routers (/market-data/quote, /market-data/history, /benchmarks, /portfolios/{id}/valuation, /portfolios/{id}/returns)
- [x] Test suite verification (8 new tests, 48 total tests passing)

---

## Phase 4 — Risk Engine ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Database models (RiskMetrics)
- [x] Alembic migration generation and verification (`506f33441a55_create_risk_metrics_table.py`)
- [x] Pydantic schemas (SeriesData, RiskMetricsDetails, RiskResponse, VaRResponse, HoldingRiskContribution, RiskContributionsResponse)
- [x] Implement Risk Engine Service (annualized returns, volatility, Sharpe, Sortino, Beta, Alpha, Tracking Error, Information Ratio, drawdown analysis, daily VaR & CVaR)
- [x] Value-at-Risk computation details (Historical, Gaussian Parametric, Monte Carlo simulations with 5,000 runs)
- [x] Holding risk contributions / Euler decomposition calculation
- [x] API endpoints (`GET /api/v1/portfolios/{id}/risk`, `/risk/var`, `/risk/contributions`)
- [x] Test suite verification (6 new tests, 54 total tests passing)

---

## Phase 5 — Benchmark Engine ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Database models (BenchmarkComparison)
- [x] Alembic migration generation and verification (`08c8ab56c54d_create_benchmark_comparisons_table.py`)
- [x] Pydantic schemas (ComparisonSeries, PeriodReturnItem, PeriodReturns, BenchmarkMetrics, BenchmarkComparisonResponse)
- [x] Implement Benchmark Engine Service (active return, tracking error, information ratio, Alpha/Beta calculation, upside/downside capture ratios)
- [x] Rolling stats calculation (60-day rolling Alpha, rolling Beta, rolling Correlation series)
- [x] Cumulative comparison growth index and specific period return calculations (1m, 3m, 6m, 1y, YTD)
- [x] API endpoints (`GET /api/v1/portfolios/{id}/benchmark`)
- [x] Test suite verification (2 new tests, 56 total tests passing)

---

## Phase 6 — Portfolio Health Score ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Database models (`HealthScore` model, registered in `__init__.py`)
- [x] Alembic migration generation and verification (`d7d491041870_create_health_scores_table.py`)
- [x] Pydantic schemas (summaries, subscores, categories, recommendations)
- [x] Implement Portfolio Health Score Service (weighted heuristics, average off-diagonal asset correlation matrix, recommendations prioritization, database caching)
- [x] API endpoints (`GET /portfolios/{id}/health`, `POST /portfolios/{id}/health/refresh`)
- [x] Test suite verification (4 new tests, 60 total tests passing)

---

## Phase 7 — Dashboard ✅

**Status**: Complete  
**Date**: 2026-06-12

Scope:
- [x] Bootstrapped Next.js 14+ App Router project in the `frontend` workspace folder
- [x] Configured premium dark mode stylesheet theme, typography (*Outfit* & *Inter*), and utility classes in `globals.css`
- [x] central API integration utility (`src/lib/api.ts`) managing auto Bearer token header injection and token refreshes
- [x] Context provider (`src/context/AuthContext.tsx`) managing sign up, login, logout, and gates
- [x] Page views for login/register credentials forms and dynamic active session detection
- [x] Responsive navigation sidebar, portfolio selector dropdown, manual holding editor forms, CSV upload modal dialogs
- [x] Dynamic area, line, donut, and bar charts powered by Recharts (valuation growth, sector weights, capture ratios, rolling alpha/beta, Euler risk decompositions)
- [x] Health radial score indicators, subscore grids, and context prioritized warnings/recommendations
- [x] Validated production Next.js build compilation (`npm run build`)

---

## Phase 8 — Optimization Engine ✅

**Status**: Complete  
**Date**: 2026-09-24

Scope:
- [x] Database models (`OptimizationRun` model, registered in `backend/app/models/__init__.py`)
- [x] Alembic migration generation and verification (`2c63ac596416_create_optimization_runs_table.py`)
- [x] Pydantic schemas (`OptimizationConstraints`, `OptimizationRequest`, `BlackLittermanView`, `BlackLittermanRequest`, `TradeRecommendation`, `ExpectedMetrics`, `EfficientFrontierData`, `OptimizationResponseData`, `OptimizationResponse`)
- [x] Institutional Optimization Engine Service (`backend/app/services/optimization_engine.py`):
  - [x] Maximum Sharpe Ratio (Tangency portfolio with Ledoit-Wolf shrinkage covariance)
  - [x] Global Minimum Variance optimization
  - [x] Mean-Variance quadratic utility optimization
  - [x] Hierarchical Risk Parity / Equal Risk Contribution (HRP / ERC)
  - [x] Black-Litterman model with user absolute and relative views, equilibrium priors ($\pi$), and posterior covariance ($\Sigma_{BL}$)
  - [x] Dynamic Markowitz Efficient Frontier curve generator
  - [x] Trade rebalancing orders generator with buy/sell/hold actions, deltas, and estimated capital
  - [x] Allocation constraints support (min/max weights, sector exposure limits)
- [x] API endpoints (`POST /api/v1/portfolios/{id}/optimize`, `POST /api/v1/portfolios/{id}/optimize/black-litterman`, `GET /api/v1/portfolios/{id}/optimize/history`)
- [x] Frontend interactive dashboard integration:
  - [x] TypeScript interfaces in `frontend/src/types/optimization.ts`
  - [x] API client helper functions in `frontend/src/lib/api.ts`
  - [x] Optimization navigation tab and dashboard view in `frontend/src/app/page.tsx`
  - [x] Method selector with parameter sliders (min/max weight constraints)
  - [x] Black-Litterman interactive view builder (absolute and relative views with confidence slider)
  - [x] Performance metrics comparison cards (Expected Return, Volatility, Sharpe)
  - [x] Recharts Markowitz Efficient Frontier scatter/line plot with current vs optimal markers
  - [x] Current vs Optimal allocation comparative bar chart
  - [x] Rebalancing trade execution order tickets table
- [x] Test suite verification (6 new comprehensive tests, 66 total tests passing)
- [x] Production build validation (`npm run build` passing cleanly)

---

## Phase 9 — Stress Testing ✅

**Status**: Complete  
**Date**: 2026-09-26

Scope:
- [x] Database models (`StressTestResult` model, registered in `backend/app/models/__init__.py`)
- [x] Alembic migration generation and verification (`3e8f7a1b2c4d_create_stress_test_results_table.py`)
- [x] Pydantic schemas (`ScenarioInfo`, `StressTestRequest`, `HoldingImpact`, `SectorImpact`, `ScenarioResult`, `StressTestResponse`, `StressTestHistoryItem`)
- [x] Institutional Stress Testing Engine Service (`backend/app/services/stress_testing_engine.py`):
  - [x] Four historical crisis scenarios (GFC 2008, COVID-19 2020, High Inflation 2022, Rate Shock 2022-23)
  - [x] Historical price fetching via market data service with scenario-specific date windows
  - [x] Per-holding return, portfolio-weighted return, max drawdown, and recovery days computation
  - [x] Sector-level impact aggregation
  - [x] Executive narrative summary generation
  - [x] Database persistence with calculation history
- [x] API endpoints (`POST /api/v1/portfolios/{id}/stress-test`, `GET /api/v1/portfolios/stress-test/scenarios`, `GET /api/v1/portfolios/{id}/stress-test/history`)
- [x] Frontend interactive dashboard integration:
  - [x] TypeScript interfaces in `frontend/src/types/stress_test.ts`
  - [x] API client helper functions in `frontend/src/lib/api.ts`
  - [x] Stress Testing navigation tab and dashboard view in `frontend/src/app/page.tsx`
  - [x] Scenario selection cards with visual feedback
  - [x] Summary cards (Portfolio Return, Max Drawdown, Recovery Days)
  - [x] Holding Impact Analysis table (scenario, ticker, return, weight, contribution)
  - [x] Sector Impact Distribution pie chart
  - [x] Narrative summary per scenario
  - [x] Stress Test History table with clickable rows
- [x] Test suite verification (8 new comprehensive tests, 74 total tests passing)
- [x] Production build validation (`npm run build` passing cleanly)

---

## Phase 10 — AI Copilot ⏳
## Phase 11 — News Intelligence ⏳
## Phase 12 — Reporting Engine ⏳


