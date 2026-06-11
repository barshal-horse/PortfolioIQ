"""Risk metrics model — stores calculated historical risk details for portfolios."""

import uuid
from datetime import date, datetime
from sqlalchemy import DateTime, Date, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class RiskMetrics(Base, UUIDMixin, TimestampMixin):
    """Calculated risk metrics for a portfolio."""

    __tablename__ = "risk_metrics"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calculation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=252)
    risk_free_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.05)

    # Core metrics
    annualized_return: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    annualized_volatility: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    beta: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    alpha: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)  # Jensen's alpha
    information_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    tracking_error: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Drawdown metrics
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_drawdown_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Tail risk
    var_95: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    var_99: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    cvar_95: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    cvar_99: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Additional
    downside_deviation: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    skewness: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    kurtosis: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Benchmark used
    benchmark: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Full return series (for charting)
    # returns dict with {"dates": [...], "values": [...]}
    return_series: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # returns dict with {"dates": [...], "values": [...]}
    drawdown_series: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # General metadata
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )

    # Relationship
    portfolio = relationship("Portfolio", backref="risk_metrics_records")

    def __repr__(self) -> str:
        return f"<RiskMetrics portfolio={self.portfolio_id} date={self.calculation_date} sharpe={self.sharpe_ratio}>"
