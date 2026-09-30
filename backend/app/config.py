"""PortfolioIQ backend configuration.

Uses pydantic-settings to load from environment variables / .env file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://portfolioiq:portfolioiq_pass@localhost:5432/portfolioiq"
    )

    # ── Auth ──────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-to-a-random-secret-key-at-least-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── App ───────────────────────────────────────────────────────────────
    default_currency: str = "USD"
    risk_free_rate: float = 0.05
    app_name: str = "PortfolioIQ"
    debug: bool = False

    # Comma-separated extra CORS origins for non-local deployments,
    # e.g. "https://app.example.com,https://www.example.com"
    cors_extra_origins: str = ""

    # ── Rate Limiting ─────────────────────────────────────────────────────
    rate_limit_general: str = "100/minute"
    rate_limit_analytics: str = "20/minute"
    rate_limit_upload: str = "5/minute"

    # ── File Upload ───────────────────────────────────────────────────────
    max_upload_size_mb: int = 10
    max_csv_rows: int = 500

    # ── Market Data (Phase 3+) ───────────────────────────────────────────
    alpha_vantage_api_key: str | None = None
    fmp_api_key: str | None = None

    # ── AI (Phases 10-12) ────────────────────────────────────────────────
    gemini_api_key: str | None = None

    # ── News (Phase 11) ──────────────────────────────────────────────────
    finnhub_api_key: str | None = None
    newsapi_api_key: str | None = None

    # ── Reports (Phase 12) ───────────────────────────────────────────────
    reports_dir: str = "reports"

    # ── Firebase Auth (Google sign-in) ───────────────────────────────────
    # Project ID used to verify Firebase ID tokens against:
    # https://securetoken.google.com/<firebase_project_id>/tokens
    firebase_project_id: str | None = None

    # ── Alpaca Broker Sync ───────────────────────────────────────────────
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
