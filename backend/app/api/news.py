"""News API endpoints — portfolio news, sentiment, and earnings."""

from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.services.news.news_service import news_service
from app.services.news.sentiment_service import sentiment_service

router = APIRouter(prefix="/news", tags=["News Intelligence"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────

from pydantic import BaseModel, Field


class NewsArticleResponse(BaseModel):
    id: UUID
    source: str
    title: str
    summary: Optional[str]
    url: str
    image_url: Optional[str]
    author: Optional[str]
    published_at: datetime
    category: Optional[str]
    related_tickers: List[str]
    raw_data: dict

    class Config:
        from_attributes = True


class SentimentScoreResponse(BaseModel):
    id: UUID
    article_id: UUID
    ticker: Optional[str]
    sentiment: str
    confidence: float
    impact_score: Optional[float]
    analysis: Optional[str]
    model_used: str
    created_at: datetime

    class Config:
        from_attributes = True


class TickerSentimentResponse(BaseModel):
    ticker: str
    overall_sentiment: str
    avg_confidence: float
    avg_impact_score: float
    article_count: int
    distribution: dict
    trend: List[dict]


class NewsFetchResult(BaseModel):
    fetched: int
    stored: int
    tickers: List[str]


# ── Portfolio News Endpoints ──────────────────────────────────────────────

@router.get(
    "/portfolio/{portfolio_id}",
    response_model=SuccessResponse[List[NewsArticleResponse]],
)
async def get_portfolio_news(
    portfolio_id: UUID,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get news articles relevant to a portfolio's holdings."""
    articles = await news_service.get_portfolio_news(
        db, portfolio_id, str(current_user.id), days, limit, offset
    )
    return SuccessResponse(data=[NewsArticleResponse.model_validate(a) for a in articles])


@router.get(
    "/ticker/{ticker}",
    response_model=SuccessResponse[List[NewsArticleResponse]],
)
async def get_ticker_news(
    ticker: str,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get news articles for a specific ticker."""
    articles = await news_service.get_ticker_news(db, ticker.upper(), days, limit)
    return SuccessResponse(data=[NewsArticleResponse.model_validate(a) for a in articles])


@router.post(
    "/portfolio/{portfolio_id}/refresh",
    response_model=SuccessResponse[NewsFetchResult],
)
async def refresh_portfolio_news(
    portfolio_id: UUID,
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger news fetch for a portfolio."""
    result = await news_service.fetch_and_store_portfolio_news(
        db=db,
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        days=days,
    )
    return SuccessResponse(data=NewsFetchResult(**result))


# ── Sentiment Endpoints ───────────────────────────────────────────────────

@router.get(
    "/sentiment/ticker/{ticker}",
    response_model=SuccessResponse[TickerSentimentResponse],
)
async def get_ticker_sentiment(
    ticker: str,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated sentiment analysis for a ticker."""
    sentiment = await sentiment_service.get_ticker_sentiment(
        db, ticker.upper(), days
    )
    return SuccessResponse(data=TickerSentimentResponse(**sentiment))


@router.get(
    "/sentiment/portfolio/{portfolio_id}",
    response_model=SuccessResponse[List[TickerSentimentResponse]],
)
async def get_portfolio_sentiment(
    portfolio_id: UUID,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sentiment summary for all holdings in a portfolio."""
    sentiments = await sentiment_service.get_portfolio_sentiment(
        db, portfolio_id, str(current_user.id), days
    )
    return SuccessResponse(data=[TickerSentimentResponse(**s) for s in sentiments])


@router.post(
    "/sentiment/process",
    response_model=SuccessResponse[dict],
)
async def trigger_sentiment_processing(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger sentiment analysis for unanalyzed articles."""
    processed = await sentiment_service.process_unanalyzed_articles(db, limit)
    return SuccessResponse(data={"processed": processed})


# ── Earnings Calendar ─────────────────────────────────────────────────────

@router.get(
    "/earnings/portfolio/{portfolio_id}",
    response_model=SuccessResponse[List[dict]],
)
async def get_earnings_calendar(
    portfolio_id: UUID,
    days_ahead: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get upcoming earnings for portfolio holdings."""
    earnings = await news_service.get_earnings_calendar(
        db, portfolio_id, str(current_user.id), days_ahead
    )
    return SuccessResponse(data=earnings)