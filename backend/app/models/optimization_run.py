"""Optimization run model — stores portfolio optimization runs, weights, efficient frontier, and recommendations."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class OptimizationRun(Base, UUIDMixin, TimestampMixin):
    """Execution run and result set for portfolio optimization."""

    __tablename__ = "optimization_runs"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    calculation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Constraints applied
    constraints: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Allocations
    current_weights: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    optimal_weights: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Optimal metrics
    expected_return: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    expected_volatility: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    expected_sharpe: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Current metrics for comparison
    current_metrics: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )

    # Recommended trade rebalancing list
    trades: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    # Efficient frontier curve points
    efficient_frontier: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Black-Litterman specific
    views: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    posterior_returns: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="completed",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )

    # Relationships
    portfolio = relationship("Portfolio", backref="optimization_runs")

    def __repr__(self) -> str:
        return f"<OptimizationRun id={self.id} method={self.method} portfolio={self.portfolio_id} sharpe={self.expected_sharpe}>"
