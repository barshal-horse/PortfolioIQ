# PortfolioIQ — System Architecture

> Institutional-Grade AI Portfolio Analyzer & Optimizer

---

## 1. Architecture Overview

PortfolioIQ is a three-tier application with an AI agent orchestration layer:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION TIER                            │
│                    Next.js 14+ (App Router)                         │
│              Tailwind CSS · Shadcn UI · Recharts                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS / REST / SSE
┌──────────────────────────▼──────────────────────────────────────────┐
│                        APPLICATION TIER                              │
│                      FastAPI (Python 3.11+)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Portfolio │ │  Market  │ │   Risk   │ │Benchmark │ │  Health  │  │
│  │ Service  │ │  Data    │ │  Engine  │ │  Engine  │ │  Score   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │Optimize  │ │  Stress  │ │   News   │ │Reporting │ │   AI     │  │
│  │ Engine   │ │  Testing │ │  Intel   │ │  Engine  │ │ Copilot  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │              LangGraph Agent Orchestration Layer              │    │
│  │    Copilot Router → Specialized Agents → Tool Execution      │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────┬───────────────────┬──────────────────────┬───────────────────┘
       │                   │                      │
┌──────▼──────┐   ┌───────▼───────┐      ┌───────▼───────┐
│ PostgreSQL  │   │  Qdrant       │      │ External APIs │
│ (Primary DB)│   │  (Vector DB)  │      │ yfinance      │
│             │   │  Local Mode   │      │ Finnhub       │
│             │   │               │      │ NewsAPI       │
└─────────────┘   └───────────────┘      │ Gemini API    │
                                         └───────────────┘
```

---

## 2. Technology Stack

### Frontend

| Technology       | Version  | Purpose                              |
|-----------------|----------|--------------------------------------|
| Next.js          | 14+      | React framework, App Router, SSR     |
| TypeScript       | 5.x      | Type safety                          |
| Tailwind CSS     | 3.x      | Utility-first styling                |
| Shadcn UI        | latest   | Component library (Radix primitives) |
| Recharts         | 2.x      | Chart visualizations                 |
| TanStack Query   | 5.x      | Server state management & caching    |
| Zustand          | 4.x      | Client state management              |
| React Hook Form  | 7.x      | Form handling with Zod validation    |
| Zod              | 3.x      | Schema validation                    |
| Lucide React     | latest   | Icon library                         |

### Backend

| Technology       | Version  | Purpose                              |
|-----------------|----------|--------------------------------------|
| Python           | 3.11+    | Runtime                              |
| FastAPI          | 0.110+   | HTTP framework, async, OpenAPI docs  |
| Uvicorn          | 0.27+    | ASGI server                          |
| SQLAlchemy       | 2.0+     | ORM (async support)                  |
| Alembic          | 1.13+    | Database migrations                  |
| Pydantic         | 2.x      | Data validation / serialization      |
| yfinance         | 0.2+     | Market data (primary)                |
| PyPortfolioOpt   | 1.5+     | Portfolio optimization               |
| CVXPY            | 1.4+     | Convex optimization solver           |
| NumPy            | 1.26+    | Numerical computing                  |
| Pandas           | 2.x      | Data manipulation                    |
| SciPy            | 1.12+    | Statistical functions                |
| python-jose      | 3.x      | JWT token handling                   |
| passlib          | 1.7+     | Password hashing (bcrypt)            |
| APScheduler      | 3.10+    | Scheduled background jobs            |
| ReportLab        | 4.x      | PDF generation                       |
| httpx            | 0.27+    | Async HTTP client                    |

### AI / Agent Layer

| Technology       | Version  | Purpose                              |
|-----------------|----------|--------------------------------------|
| LangGraph        | 0.2+     | Agent state machine orchestration    |
| LangChain Core   | 0.2+     | Base abstractions (messages, tools)  |
| Google GenAI     | 0.5+     | Gemini API client                    |
| Qdrant Client    | 1.8+     | Vector database client               |
| Qdrant (Server)  | 1.8+     | Local vector DB (Docker)             |

### Infrastructure

| Technology       | Version  | Purpose                              |
|-----------------|----------|--------------------------------------|
| PostgreSQL       | 16       | Primary relational database          |
| Qdrant           | 1.8+     | Vector storage (local Docker)        |
| Docker           | 24+      | Containerization                     |
| Docker Compose   | 2.x      | Multi-service orchestration          |

---

## 3. Service Layer Architecture

Each service is a self-contained module with clear inputs, outputs, and dependencies.

### 3.1 Portfolio Service

**Purpose**: CRUD operations for portfolios, holdings, and transactions.

```
Responsibilities:
├── Portfolio CRUD (create, read, update, delete)
├── Holdings management (add, update, remove, bulk import)
├── CSV upload parsing and validation
├── Manual holdings entry
├── Portfolio snapshot generation
├── Weight calculation and normalization
└── Transaction history tracking
```

**Dependencies**: PostgreSQL  
**Consumed by**: All analytics services, AI agents

### 3.2 Market Data Service

**Purpose**: Fetch, cache, and serve market data from external providers.

```
Responsibilities:
├── Historical price data (yfinance — primary)
├── Real-time quotes (yfinance)
├── Daily return calculation
├── Portfolio valuation (mark-to-market)
├── Benchmark index data (Nifty50, Sensex, S&P500, Nasdaq100)
├── Dividend and split data
├── Instrument metadata (sector, industry, market cap)
├── Data caching with staleness detection
└── Fallback chain: yfinance → Alpha Vantage → FMP
```

**External APIs**: yfinance (primary), Alpha Vantage (fallback), Financial Modeling Prep (fallback)  
**Caching**: Database-backed with TTL (prices: 15 min, daily: EOD, metadata: 24h)

### 3.3 Risk Engine

**Purpose**: Compute institutional-grade risk metrics.

```
Metrics:
├── Annualized Volatility (σ)
├── Sharpe Ratio = (Rp − Rf) / σp
├── Sortino Ratio = (Rp − Rf) / σd  (downside deviation)
├── Beta = Cov(Rp, Rm) / Var(Rm)
├── Jensen's Alpha = Rp − [Rf + β(Rm − Rf)]
├── Information Ratio = (Rp − Rb) / TE
├── Tracking Error = σ(Rp − Rb)
├── Maximum Drawdown = max peak-to-trough decline
├── Value at Risk (VaR) — Historical simulation, 95% & 99%
└── Conditional VaR (CVaR / ES) — Expected Shortfall
```

**Dependencies**: Market Data Service, Portfolio Service  
**Parameters**: Lookback period (configurable), risk-free rate (auto-fetched or manual)

### 3.4 Benchmark Engine

**Purpose**: Compare portfolio performance against market benchmarks.

```
Benchmarks Supported:
├── ^NSEI  — Nifty 50 (India)
├── ^BSESN — Sensex (India)
├── ^GSPC  — S&P 500 (US)
└── ^NDX   — Nasdaq 100 (US)

Metrics:
├── Active Return = Rp − Rb
├── Tracking Error = σ(Rp − Rb)
├── Alpha (Jensen's)
├── Information Ratio
├── Upside Capture Ratio = Rp_up / Rb_up
└── Downside Capture Ratio = Rp_down / Rb_down
```

**Dependencies**: Market Data Service, Risk Engine

### 3.5 Portfolio Health Score Engine

**Purpose**: Generate a composite health score (0–100) with subscores and explanations.

```
Score Composition:
├── Overall Score (0–100, weighted average)
│   ├── Diversification Score (25%)
│   │   ├── HHI (Herfindahl-Hirschman Index)
│   │   ├── Sector concentration
│   │   ├── Number of holdings
│   │   └── Correlation analysis
│   ├── Risk Score (30%)
│   │   ├── Volatility relative to benchmark
│   │   ├── Maximum drawdown severity
│   │   ├── VaR breach frequency
│   │   └── Tail risk assessment
│   ├── Performance Score (25%)
│   │   ├── Absolute returns (1M, 3M, 6M, 1Y, 3Y)
│   │   ├── Risk-adjusted returns (Sharpe, Sortino)
│   │   └── Consistency of returns
│   └── Efficiency Score (20%)
│       ├── Sharpe ratio vs benchmark Sharpe
│       ├── Information ratio
│       └── Return per unit of risk
└── Natural language explanations for each subscore
```

### 3.6 Optimization Engine

**Purpose**: Generate optimal portfolio allocations using multiple methods.

```
Methods:
├── Mean-Variance Optimization (Markowitz)
├── Maximum Sharpe Ratio
├── Minimum Variance
├── Risk Parity (Equal Risk Contribution)
└── Black-Litterman (with views)

Output:
├── Recommended allocation weights
├── Expected return
├── Expected risk (volatility)
├── Efficient frontier data points
├── Trade recommendations (current → optimal)
└── Constraint satisfaction report
```

**Libraries**: PyPortfolioOpt, CVXPY  
**Constraints**: Min/max position sizes, sector limits, turnover constraints

### 3.7 Stress Testing Engine

**Purpose**: Simulate portfolio impact under historical and hypothetical scenarios.

```
Historical Scenarios:
├── 2008 Global Financial Crisis (Sep 2008 – Mar 2009)
├── COVID-19 Crash (Feb 2020 – Mar 2020)
├── High Inflation (2022 regime)
└── Interest Rate Shock (2022–2023 rate hikes)

Output per Scenario:
├── Portfolio return during scenario period
├── Maximum drawdown during scenario
├── Recovery time estimate
├── Worst-performing holdings
├── Sector-level impact breakdown
└── Comparison with benchmark performance
```

### 3.8 News Intelligence Service

**Purpose**: Aggregate, analyze, and score news for portfolio holdings.

```
Sources:
├── Finnhub (company news, earnings)
└── NewsAPI (general financial news)

Features:
├── Holdings-specific news filtering
├── Earnings calendar and surprises
├── Sentiment analysis (Gemini-powered)
├── Portfolio impact assessment
└── News relevance scoring
```

### 3.9 Reporting Engine

**Purpose**: Generate professional PDF reports.

```
Report Types:
├── Executive Summary (1-page overview)
├── Full Portfolio Report
│   ├── Holdings breakdown
│   ├── Performance summary
│   ├── Risk metrics
│   ├── Benchmark comparison
│   └── Health score
├── Monthly Review
└── Portfolio Health Report

Output: PDF (via ReportLab)
```

### 3.10 AI Copilot Service

**Purpose**: Natural language interface to all analytics via LangGraph agents.

```
Capabilities:
├── Route queries to specialized agents
├── Multi-agent collaboration for complex queries
├── Citation and reasoning chains
├── Conversation memory (PostgreSQL + Qdrant)
├── "Not financial advice" guardrails
└── Streaming responses (SSE)
```

---

## 4. Data Flow Architecture

### 4.1 Portfolio Upload Flow

```
User uploads CSV / enters holdings manually
         │
         ▼
┌─────────────────┐
│  Input Parser   │──── CSV: parse columns, detect format
│                 │──── Manual: validate ticker, qty, price
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validator      │──── Check ticker exists (yfinance lookup)
│                 │──── Validate quantities (positive, non-zero)
│                 │──── Detect duplicates
│                 │──── Currency normalization
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Enrichment     │──── Fetch sector, industry, market cap
│                 │──── Fetch latest price
│                 │──── Calculate current value & weight
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Persistence    │──── Save to portfolios + holdings tables
│                 │──── Generate portfolio snapshot
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analytics      │──── Trigger async analytics pipeline
│  Trigger        │──── Risk, Benchmark, Health Score
└─────────────────┘
```

### 4.2 Analytics Pipeline Flow

```
Portfolio Created/Updated
         │
         ▼
┌────────────────────────────────────────────┐
│          Analytics Pipeline                 │
│                                            │
│  1. Fetch historical prices (Market Data)  │
│  2. Calculate daily returns                │
│  3. Compute risk metrics (Risk Engine)     │
│  4. Run benchmark comparison               │
│  5. Generate health score                  │
│  6. Cache results in analytics tables      │
│                                            │
│  Runs: On-demand + daily scheduled update  │
└────────────────────────────────────────────┘
```

### 4.3 AI Copilot Flow

```
User sends natural language query
         │
         ▼
┌─────────────────┐
│  Copilot Router │──── Intent classification (Gemini)
│  (LangGraph)    │──── Determine which agent(s) to invoke
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Risk   │ │Bench.  │ │Health  │ │Optim.  │
│ Agent  │ │Agent   │ │Agent   │ │Agent   │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │
    └────┬─────┴──────────┴──────────┘
         │
         ▼
┌─────────────────┐
│  Response       │──── Aggregate results
│  Synthesizer    │──── Add citations
│                 │──── Apply guardrails
│                 │──── Stream to frontend (SSE)
└─────────────────┘
```

---

## 5. Caching Strategy

No Redis. Caching uses a two-tier approach:

### Tier 1: In-Memory Cache (TTLCache)

```python
# Using cachetools for simple in-memory caching
from cachetools import TTLCache

CACHES = {
    "quotes":      TTLCache(maxsize=500, ttl=900),     # 15 min
    "metadata":    TTLCache(maxsize=1000, ttl=86400),   # 24 hours
    "risk_metrics": TTLCache(maxsize=200, ttl=3600),    # 1 hour
}
```

### Tier 2: Database-Backed Cache

```
Table: cache_entries
├── key (VARCHAR, PRIMARY KEY)
├── value (JSONB)
├── created_at (TIMESTAMP)
├── expires_at (TIMESTAMP)
└── category (VARCHAR) — for bulk invalidation
```

**Cache Invalidation Rules**:
- Market data: Stale after market close + 30 min
- Analytics: Invalidated on portfolio modification
- Metadata: Refresh daily

---

## 6. Background Job Architecture

No Celery. Uses FastAPI's built-in background tasks + APScheduler for scheduled jobs.

### On-Demand Background Tasks

```python
from fastapi import BackgroundTasks

@router.post("/portfolios/{id}/analyze")
async def trigger_analysis(id: UUID, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_analytics_pipeline, portfolio_id=id)
    return {"status": "analysis_started"}
```

### Scheduled Jobs (APScheduler)

```
Daily Jobs:
├── 06:00 UTC — Refresh market data for all active portfolios
├── 06:30 UTC — Recalculate risk metrics
├── 07:00 UTC — Update benchmark comparisons
├── 07:30 UTC — Regenerate health scores
└── 08:00 UTC — Fetch and analyze news
```

---

## 7. Security Architecture

### Authentication

```
Method: JWT (JSON Web Tokens)
├── Access token: 30 min TTL
├── Refresh token: 7 day TTL
├── Password hashing: bcrypt (via passlib)
└── Token storage: httpOnly cookies (frontend)
```

### API Key Management

```
External API Keys (environment variables):
├── GEMINI_API_KEY
├── ALPHA_VANTAGE_API_KEY
├── FMP_API_KEY
├── FINNHUB_API_KEY
├── NEWSAPI_API_KEY
└── DATABASE_URL
```

### Rate Limiting

```
Per-user limits:
├── General API: 100 req/min
├── Analytics: 20 req/min
├── AI Copilot: 10 req/min
├── Market Data: 30 req/min
└── Report Generation: 5 req/min

Implementation: slowapi (built on limits library)
```

### Input Validation

```
All inputs validated via Pydantic models:
├── Ticker symbols: regex validated, length-limited
├── Quantities: positive numeric, bounded
├── Dates: ISO format, range-checked
├── File uploads: size limit (10MB), type check (.csv)
└── Chat messages: length limit (2000 chars)
```

---

## 8. Deployment Topology

### Local Development (Docker Compose)

```yaml
services:
  frontend:        # Next.js dev server — port 3000
  backend:         # FastAPI + Uvicorn — port 8000
  postgres:        # PostgreSQL 16 — port 5432
  qdrant:          # Qdrant vector DB — port 6333
```

### Environment Variables

```
# Database
DATABASE_URL=postgresql+asyncpg://portfolioiq:password@postgres:5432/portfolioiq

# LLM
GEMINI_API_KEY=<your-key>

# Market Data
ALPHA_VANTAGE_API_KEY=<your-key>
FMP_API_KEY=<your-key>

# News
FINNHUB_API_KEY=<your-key>
NEWSAPI_API_KEY=<your-key>

# Auth
JWT_SECRET_KEY=<generated-secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# App
RISK_FREE_RATE=0.05
DEFAULT_CURRENCY=USD
```

---

## 9. Project Directory Structure

```
portfolioiq/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── docs/                              # Architecture documents (Phase 1)
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPECIFICATION.md
│   ├── LANGGRAPH_ARCHITECTURE.md
│   └── MASTER_BUILD_PLAN.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                  # Migration files
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings (pydantic-settings)
│   │   ├── dependencies.py            # Dependency injection
│   │   │
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── portfolio.py
│   │   │   ├── holding.py
│   │   │   ├── transaction.py
│   │   │   ├── instrument.py
│   │   │   ├── price_history.py
│   │   │   ├── analytics.py
│   │   │   ├── benchmark.py
│   │   │   ├── news.py
│   │   │   ├── agent.py
│   │   │   └── report.py
│   │   │
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── portfolio.py
│   │   │   ├── holding.py
│   │   │   ├── market_data.py
│   │   │   ├── risk.py
│   │   │   ├── benchmark.py
│   │   │   ├── health_score.py
│   │   │   ├── optimization.py
│   │   │   ├── stress_test.py
│   │   │   ├── copilot.py
│   │   │   ├── news.py
│   │   │   └── report.py
│   │   │
│   │   ├── api/                       # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── router.py              # Aggregate router
│   │   │   ├── auth.py
│   │   │   ├── portfolios.py
│   │   │   ├── holdings.py
│   │   │   ├── market_data.py
│   │   │   ├── risk.py
│   │   │   ├── benchmarks.py
│   │   │   ├── health_score.py
│   │   │   ├── optimization.py
│   │   │   ├── stress_testing.py
│   │   │   ├── copilot.py
│   │   │   ├── news.py
│   │   │   └── reports.py
│   │   │
│   │   ├── services/                  # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── portfolio_service.py
│   │   │   ├── market_data_service.py
│   │   │   ├── risk_engine.py
│   │   │   ├── benchmark_engine.py
│   │   │   ├── health_score_engine.py
│   │   │   ├── optimization_engine.py
│   │   │   ├── stress_testing_engine.py
│   │   │   ├── news_service.py
│   │   │   ├── reporting_engine.py
│   │   │   └── cache_service.py
│   │   │
│   │   ├── agents/                    # LangGraph agents
│   │   │   ├── __init__.py
│   │   │   ├── copilot.py             # Main router agent
│   │   │   ├── risk_agent.py
│   │   │   ├── benchmark_agent.py
│   │   │   ├── health_agent.py
│   │   │   ├── optimization_agent.py
│   │   │   ├── stress_testing_agent.py
│   │   │   ├── news_agent.py
│   │   │   ├── reporting_agent.py
│   │   │   ├── diversification_agent.py
│   │   │   ├── sentiment_agent.py
│   │   │   ├── performance_agent.py
│   │   │   ├── goal_planning_agent.py
│   │   │   ├── tools/                 # Agent tools (callables)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── risk_tools.py
│   │   │   │   ├── benchmark_tools.py
│   │   │   │   ├── portfolio_tools.py
│   │   │   │   ├── market_tools.py
│   │   │   │   ├── optimization_tools.py
│   │   │   │   └── news_tools.py
│   │   │   ├── state.py               # LangGraph state definitions
│   │   │   ├── prompts.py             # System prompts & templates
│   │   │   └── guardrails.py          # Safety filters
│   │   │
│   │   └── utils/                     # Shared utilities
│   │       ├── __init__.py
│   │       ├── csv_parser.py
│   │       ├── calculations.py
│   │       ├── formatters.py
│   │       └── constants.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                # Shared fixtures
│       ├── test_portfolio_service.py
│       ├── test_market_data_service.py
│       ├── test_risk_engine.py
│       ├── test_benchmark_engine.py
│       ├── test_health_score_engine.py
│       ├── test_optimization_engine.py
│       ├── test_stress_testing.py
│       ├── test_news_service.py
│       ├── test_reporting.py
│       ├── test_api_portfolios.py
│       ├── test_api_auth.py
│       └── test_agents/
│           ├── test_copilot.py
│           ├── test_risk_agent.py
│           └── test_benchmark_agent.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   │
│   ├── public/
│   │   └── assets/
│   │
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Landing / redirect
│   │   │   ├── globals.css
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx           # Portfolio Overview
│   │   │   │   ├── risk/page.tsx      # Risk Analytics
│   │   │   │   ├── benchmarks/page.tsx
│   │   │   │   ├── health/page.tsx
│   │   │   │   ├── optimize/page.tsx
│   │   │   │   ├── stress-test/page.tsx
│   │   │   │   ├── news/page.tsx
│   │   │   │   └── reports/page.tsx
│   │   │   └── copilot/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                    # Shadcn components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Footer.tsx
│   │   │   ├── portfolio/
│   │   │   │   ├── PortfolioTable.tsx
│   │   │   │   ├── UploadCSV.tsx
│   │   │   │   ├── AddHolding.tsx
│   │   │   │   └── PortfolioSummary.tsx
│   │   │   ├── charts/
│   │   │   │   ├── AllocationPie.tsx
│   │   │   │   ├── PerformanceLine.tsx
│   │   │   │   ├── DrawdownChart.tsx
│   │   │   │   ├── EfficientFrontier.tsx
│   │   │   │   └── HealthGauge.tsx
│   │   │   ├── risk/
│   │   │   │   ├── RiskDashboard.tsx
│   │   │   │   └── MetricCard.tsx
│   │   │   ├── copilot/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── SuggestedQueries.tsx
│   │   │   └── reports/
│   │   │       └── ReportGenerator.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                 # API client (fetch wrapper)
│   │   │   ├── auth.ts                # Auth helpers
│   │   │   └── utils.ts               # Shared utilities
│   │   │
│   │   ├── hooks/
│   │   │   ├── usePortfolio.ts
│   │   │   ├── useRiskMetrics.ts
│   │   │   ├── useBenchmark.ts
│   │   │   ├── useHealthScore.ts
│   │   │   └── useCopilot.ts
│   │   │
│   │   ├── stores/
│   │   │   ├── authStore.ts
│   │   │   └── portfolioStore.ts
│   │   │
│   │   └── types/
│   │       ├── portfolio.ts
│   │       ├── risk.ts
│   │       ├── benchmark.ts
│   │       ├── optimization.ts
│   │       └── copilot.ts
│   │
│   └── __tests__/
│       ├── components/
│       └── hooks/
│
└── PortfolioIQ_Documentation_Pack/    # Original reference docs
    ├── docs/
    ├── agents/
    ├── analytics/
    ├── infrastructure/
    └── testing/
```

---

## 10. Cross-Cutting Concerns

### Error Handling

```python
# Standardized error response format
{
    "error": {
        "code": "PORTFOLIO_NOT_FOUND",
        "message": "Portfolio with ID xyz not found",
        "details": {},
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

### Logging

```
Format: JSON structured logs
Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
Fields: timestamp, level, service, user_id, request_id, message, extra
Library: Python stdlib logging with JSON formatter
```

### Health Checks

```
GET /health          → Basic liveness
GET /health/ready    → Readiness (DB connected, services initialized)
GET /health/detailed → Full system status (DB, Qdrant, external APIs)
```

### CORS Configuration

```python
origins = [
    "http://localhost:3000",      # Next.js dev server
    "http://frontend:3000",       # Docker internal
]
```

---

## 11. Multi-Currency Support

```
Default: USD
Supported: USD, INR, EUR, GBP

Strategy:
├── Holdings stored in their native currency
├── Portfolio valuation converted to user's base currency
├── Exchange rates fetched via yfinance (e.g., USDINR=X)
├── Historical rates cached for performance attribution
└── Benchmark comparisons in benchmark's native currency
```

---

## 12. Performance Targets

| Metric                          | Target          |
|--------------------------------|-----------------|
| API response (simple queries)   | < 200ms         |
| API response (analytics)        | < 2s            |
| Portfolio upload (100 holdings) | < 5s            |
| Risk metrics calculation        | < 3s            |
| PDF report generation           | < 10s           |
| Copilot response (streaming)    | First token < 2s|
| Database queries                | < 100ms         |
| Dashboard page load             | < 1.5s          |
