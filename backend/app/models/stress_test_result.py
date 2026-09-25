"""Stress test results model — stores simulated scenario impacts, drawdowns, and holding contributions."""

import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class StressTestResult(Base, UUIDMixin, TimestampMixin):
    """Execution output of a stress testing scenario on a portfolio."""

    __tablename__ = "stress_test_results"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario: Mapped[str] = mapped_column(
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

    # Scenario parameters
    scenario_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Portfolio impact
    portfolio_return: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    recovery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Per-holding impact breakdown
    # [{ticker, return, contribution, weight}]
    holding_impacts: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    # Sector-level impact breakdown
    # [{sector, return, weight, contribution}]
    sector_impacts: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    # Executive narrative summary
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )

    # Relationship
    portfolio = relationship("Portfolio", backref="stress_test_results")

    def __repr__(self) -> str:
        return f"<StressTestResult id={self.id} scenario={self.scenario} return={self.portfolio_return}>"
