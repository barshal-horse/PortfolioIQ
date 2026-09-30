"""API key settings model — per-user third-party API keys (Gemini, etc.)."""

from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, TimestampMixin, UUIDMixin


class ApiKeySetting(Base, UUIDMixin, TimestampMixin):
    """Per-user API key for a third-party provider (e.g. Gemini).

    Keys are stored base64-encoded (same obfuscation policy as
    BrokerConnection) — the DB is the trust boundary.
    """

    __tablename__ = "api_key_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_api_key_user_provider"),
    )

    user_id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    key_enc: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<ApiKeySetting user={self.user_id} provider={self.provider}>"
