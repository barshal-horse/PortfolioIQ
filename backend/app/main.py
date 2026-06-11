"""PortfolioIQ — FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    print(f"🚀 PortfolioIQ backend starting...")
    print(f"📊 Debug mode: {settings.debug}")
    yield
    # Shutdown
    print("👋 PortfolioIQ backend shutting down...")


app = FastAPI(
    title="PortfolioIQ API",
    description="Institutional-Grade AI Portfolio Analyzer & Optimizer",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(api_router)


# ── Health Check Endpoints ───────────────────────────────────────────────


@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Basic liveness check."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/health/ready", tags=["System"])
async def readiness_check():
    """Readiness probe — checks DB connectivity."""
    from app.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "checks": {"database": db_status},
    }


# ── Global Exception Handler ────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a structured error response."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"type": type(exc).__name__} if settings.debug else {},
            },
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        },
    )
