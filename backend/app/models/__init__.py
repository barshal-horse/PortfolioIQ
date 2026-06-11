"""SQLAlchemy model base and registry.

All models import Base from here to share the same metadata.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


# Import all models so Alembic can discover them
from app.models.user import User  # noqa: E402, F401
from app.models.portfolio import Portfolio  # noqa: E402, F401
from app.models.instrument import Instrument  # noqa: E402, F401
from app.models.holding import Holding  # noqa: E402, F401
from app.models.transaction import Transaction  # noqa: E402, F401
from app.models.price_history import (  # noqa: E402, F401
    PriceHistory,
    Dividend,
    Split,
    ExchangeRate,
    CacheEntry,
)
from app.models.risk_metrics import RiskMetrics  # noqa: E402, F401
