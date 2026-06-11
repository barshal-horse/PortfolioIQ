# PortfolioIQ — Master Build Plan

> Institutional-Grade AI Portfolio Analyzer & Optimizer

---

## Build Priority

```
Phase 1  → Architecture & Design Documents          ✅ COMPLETE
Phase 2  → Portfolio Upload (CSV + Manual Holdings)
Phase 3  → Market Data Service (yfinance)
Phase 4  → Risk Engine (10 metrics)
Phase 5  → Benchmark Engine (4 indices, 6 metrics)
Phase 6  → Portfolio Health Score (0–100, 4 subscores)
Phase 7  → Dashboard (Overview, Risk, Benchmark, Health)
Phase 8  → Optimization Engine (5 methods)
Phase 9  → Stress Testing (4 scenarios)
Phase 10 → AI Copilot (LangGraph, 12 agents)
Phase 11 → News Intelligence (Finnhub, NewsAPI)
Phase 12 → Reporting Engine (PDF reports)
```

---

## Phase 1 Deliverables

| Document | Path | Status |
|----------|------|--------|
| System Architecture | `docs/ARCHITECTURE.md` | ✅ Complete |
| Database Schema | `docs/DATABASE_SCHEMA.md` | ✅ Complete |
| API Specification | `docs/API_SPECIFICATION.md` | ✅ Complete |
| LangGraph Architecture | `docs/LANGGRAPH_ARCHITECTURE.md` | ✅ Complete |

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14+ · Tailwind · Shadcn UI · Recharts |
| Backend | FastAPI · Python 3.11+ · SQLAlchemy 2.0 |
| Database | PostgreSQL 16 |
| Vector DB | Qdrant (local Docker) |
| LLM | Google Gemini API (AI Studio) |
| Agents | LangGraph · LangChain Core |
| Optimization | PyPortfolioOpt · CVXPY |
| Market Data | yfinance · Alpha Vantage · FMP |
| News | Finnhub · NewsAPI |
| Containerization | Docker Compose |

---

## Rules

1. Complete one phase at a time
2. Wait for approval before moving to next phase
3. Generate tests for every module
4. Keep architecture modular
5. Follow documentation strictly
6. Never skip analytics validation
7. Prioritize correctness over speed
