"""Health score model — stores portfolio health evaluations and grades."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class HealthScore(Base, UUIDMixin, TimestampMixin):
    """Calculated health scores for a portfolio."""

    __tablename__ = "health_scores"

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

    # Overall Metrics
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_grade: Mapped[str] = mapped_column(String(20), nullable=False)  # excellent, good, etc.
    overall_explanation: Mapped[str] = mapped_column(Text, nullable=False)

    # Diversification Subscore
    diversification_score: Mapped[int] = mapped_column(Integer, nullable=False)
    diversification_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    # details: {hhi, sector_concentration, num_holdings, correlation_avg, explanation}
    diversification_details: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Risk Subscore
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    # details: {vol_vs_benchmark, mdd_severity, tail_risk, explanation}
    risk_details: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Performance Subscore
    performance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    # details: {returns_1m, returns_3m, returns_1y, consistency, explanation}
    performance_details: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Efficiency Subscore
    efficiency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    efficiency_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    # details: {sharpe_vs_benchmark, information_ratio, return_per_risk, explanation}
    efficiency_details: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Recommendations
    # list of recommendations: [{priority: str, category: str, action: str, rationale: str}]
    recommendations: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )

    # Metadata
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )

    # Relationship
    portfolio = relationship("Portfolio", backref="health_scores_records")

    def __repr__(self) -> str:
        return f"<HealthScore portfolio={self.portfolio_id} score={self.overall_score} grade={self.overall_grade}>"
