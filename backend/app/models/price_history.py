"""Models for price history, dividends, splits, exchange rates, and cache entries."""

from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import CurrencyCode


class PriceHistory(Base, UUIDMixin, TimestampMixin):
    """Daily historical price data for a security."""

    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_history_ticker_date"),
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    close: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    daily_return: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)

    def __repr__(self) -> str:
        return f"<PriceHistory {self.ticker} {self.date} close={self.close}>"


class Dividend(Base, UUIDMixin, TimestampMixin):
    """Historical dividend payments."""

    __tablename__ = "dividends"
    __table_args__ = (
        UniqueConstraint("ticker", "ex_date", name="uq_dividend_ticker_ex_date"),
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )

    def __repr__(self) -> str:
        return f"<Dividend {self.ticker} {self.ex_date} amount={self.amount}>"


class Split(Base, UUIDMixin, TimestampMixin):
    """Historical stock splits."""

    __tablename__ = "splits"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_split_ticker_date"),
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    ratio: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)  # e.g., 2.0 for 2:1 split

    def __repr__(self) -> str:
        return f"<Split {self.ticker} {self.date} ratio={self.ratio}>"


class ExchangeRate(Base, UUIDMixin, TimestampMixin):
    """Daily historical currency exchange rates."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "date", name="uq_exchange_rates_pair_date"),
    )

    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.from_currency}/{self.to_currency} {self.date} rate={self.rate}>"


class CacheEntry(Base, TimestampMixin):
    """Database-backed cache table with TTL expiration support."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    value: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(astext_type=String()), "postgresql"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<CacheEntry key={self.key} category={self.category} expires={self.expires_at}>"
