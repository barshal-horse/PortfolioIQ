"""Copilot session and message models — AI conversation history."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin


class CopilotSession(Base, UUIDMixin, TimestampMixin):
    """Conversation session between user and Copilot."""

    __tablename__ = "copilot_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(astext_type=Text()), "postgresql"),
        nullable=True,
        default=dict,
    )

    messages = relationship("CopilotMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CopilotSession id={self.id} user_id={self.user_id} title={self.title}>"


class CopilotMessage(Base, UUIDMixin):
    """Individual message in a Copilot session."""

    __tablename__ = "copilot_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("copilot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_calls: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(astext_type=Text()), "postgresql"),
        nullable=False,
        default=list,
    )
    tool_results: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(astext_type=Text()), "postgresql"),
        nullable=False,
        default=list,
    )
    citations: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(astext_type=Text()), "postgresql"),
        nullable=False,
        default=list,
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int] = mapped_column(default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(default=0, nullable=False)

    session = relationship("CopilotSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<CopilotMessage id={self.id} session_id={self.session_id} role={self.role}>"