"""News and sentiment models — market intelligence data."""

import uuid
from datetime import datetime
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text, Numeric, func, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, UUIDMixin


class NewsArticle(Base, UUIDMixin):
    """News article from financial news sources."""

    __tablename__ = "news_articles"

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_tickers: Mapped[List[str]] = mapped_column(
        JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql"),
        nullable=False,
        default=list,
    )
    raw_data: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(astext_type=sa.Text()), "postgresql"),
        nullable=False,
        default=dict,
    )

    sentiments = relationship("SentimentScore", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<NewsArticle id={self.id} title={self.title[:50]} source={self.source}>"


class SentimentScore(Base, UUIDMixin):
    """Sentiment analysis score for a news article."""

    __tablename__ = "sentiment_scores"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(precision=5, scale=4), nullable=False)
    impact_score: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="gemini")

    article = relationship("NewsArticle", back_populates="sentiments")

    def __repr__(self) -> str:
        return f"<SentimentScore id={self.id} ticker={self.ticker} sentiment={self.sentiment}>"