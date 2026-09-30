"""Broker connection model — per-user broker credentials and sync metadata."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin, UUIDMixin


class BrokerConnection(Base, UUIDMixin, TimestampMixin):
    """Per-user broker credentials and sync metadata."""

    __tablename__ = "broker_connections"

    user_id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker: Mapped[str] = mapped_column(String(30), nullable=False, default="alpaca")
    # Base64-encoded API key id + secret (obfuscation only — the DB is the trust boundary;
    # encrypt at rest with a KMS key for multi-tenant production deployments).
    api_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(astext_type=Text()), "postgresql"),
        nullable=False,
        default=dict,
    )

    def __repr__(self) -> str:
        return f"<BrokerConnection user={self.user_id} broker={self.broker}>"
