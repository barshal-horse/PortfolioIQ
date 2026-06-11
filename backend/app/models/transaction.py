"""Transaction model — records buy/sell/dividend events."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import CurrencyCode, TransactionType


class Transaction(Base, UUIDMixin, TimestampMixin):
    """A historical transaction event (buy, sell, dividend, etc.)."""

    __tablename__ = "transactions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    holding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("holdings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    fees: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="transactions")
    holding = relationship("Holding", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_type} {self.ticker} qty={self.quantity}>"
