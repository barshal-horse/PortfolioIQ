"""Benchmark comparison model — stores portfolio performance comparisons against indices."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class BenchmarkComparison(Base, UUIDMixin, TimestampMixin):
    """Calculated benchmark comparisons for a portfolio."""

    __tablename__ = "benchmark_comparisons"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    benchmark: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=252)

    # Relative performance metrics
    active_return: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    tracking_error: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    information_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    alpha: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    beta: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Capture ratios
    upside_capture: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    downside_capture: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Rolling metrics (JSON series with dates & values keys)
    rolling_alpha: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    rolling_beta: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    rolling_correlation: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Cumulative returns
    portfolio_cumulative: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    benchmark_cumulative: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Specific period returns comparison (1m, 3m, 6m, 1y, ytd)
    period_returns: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # General metadata
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )

    # Relationship
    portfolio = relationship("Portfolio", backref="benchmark_comparisons")

    def __repr__(self) -> str:
        return f"<BenchmarkComparison portfolio={self.portfolio_id} benchmark={self.benchmark} calculation_date={self.calculation_date}>"
