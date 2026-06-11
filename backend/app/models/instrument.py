"""Instrument model — represents a tradable security."""

from sqlalchemy import BigInteger, Boolean, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import CurrencyCode, ExchangeCode, InstrumentType


class Instrument(Base, UUIDMixin, TimestampMixin):
    """A tradable security (stock, ETF, index, etc.)."""

    __tablename__ = "instruments"

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    instrument_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InstrumentType.EQUITY.value
    )
    exchange: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=ExchangeCode.OTHER.value
    )
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )

    def __repr__(self) -> str:
        return f"<Instrument {self.ticker}>"
