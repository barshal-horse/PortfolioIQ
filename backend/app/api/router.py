"""Aggregate API router — mounts all endpoint modules."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.portfolios import router as portfolios_router
from app.api.holdings import router as holdings_router
from app.api.market_data import router as market_data_router
from app.api.benchmarks import router as benchmarks_router
from app.api.risk import router as risk_router
from app.api.benchmark import router as benchmark_comparison_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(portfolios_router)
api_router.include_router(holdings_router)
api_router.include_router(market_data_router)
api_router.include_router(benchmarks_router)
api_router.include_router(risk_router)
api_router.include_router(benchmark_comparison_router)

# Future phases will add:
# api_router.include_router(risk_router)
# api_router.include_router(health_score_router)
# api_router.include_router(optimization_router)
# api_router.include_router(stress_testing_router)
# api_router.include_router(copilot_router)
# api_router.include_router(news_router)
# api_router.include_router(reports_router)
