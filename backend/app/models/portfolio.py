"""Portfolio model."""

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import BenchmarkType, CurrencyCode, PortfolioStatus


class Portfolio(Base, UUIDMixin, TimestampMixin):
    """Investment portfolio belonging to a user."""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_portfolio_user_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PortfolioStatus.ACTIVE.value, index=True
    )
    benchmark: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=BenchmarkType.SP500.value
    )

    # Computed portfolio-level aggregates (updated on holding changes)
    total_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    pnl_percentage: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0)

    last_analyzed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="portfolios")
    holdings = relationship(
        "Holding", back_populates="portfolio", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "Transaction", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Portfolio {self.name}>"


