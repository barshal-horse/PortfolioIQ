"""Holding model — a position in a portfolio."""

import uuid

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import CurrencyCode


class Holding(Base, UUIDMixin, TimestampMixin):
    """A single holding (position) within a portfolio."""

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", name="uq_holding_portfolio_ticker"),
    )

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id"),
        nullable=True,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    average_cost: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    current_price: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    current_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    cost_basis: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    weight: Mapped[float] = mapped_column(Numeric(8, 6), default=0.0)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )

    # Relationships
    portfolio = relationship("Portfolio", back_populates="holdings")
    instrument = relationship("Instrument")
    transactions = relationship(
        "Transaction", back_populates="holding", cascade="all, delete-orphan"
    )

    def recalculate(self) -> None:
        """Recalculate derived fields from quantity, average_cost, current_price."""
        self.cost_basis = float(self.quantity) * float(self.average_cost)
        self.current_value = float(self.quantity) * float(self.current_price)
        self.unrealized_pnl = self.current_value - self.cost_basis

    def __repr__(self) -> str:
        return f"<Holding {self.ticker} qty={self.quantity}>"
