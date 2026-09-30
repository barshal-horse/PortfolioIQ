"""Report models — generated PDF reports and metadata."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, Integer, func, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, UUIDMixin


class Report(Base, UUIDMixin):
    """Generated report metadata."""

    __tablename__ = "reports"

    # Note: reports table has created_at (server default) but no updated_at,
    # so TimestampMixin is not used here.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql"),
        nullable=False,
        default=dict,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} status={self.status}>"