"""Sentiment service — AI-powered sentiment analysis for financial news."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from google import genai
from google.genai import types
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.news import NewsArticle, SentimentScore
from app.utils.ids import to_uuid as _to_uuid


# Initialize Gemini client
_gemini_key = get_settings().gemini_api_key
client = genai.Client(api_key=_gemini_key) if _gemini_key else None

SENTIMENT_PROMPT = """You are a financial sentiment analysis expert. Analyze the sentiment of the following news article 
and determine its likely impact on the specified stock ticker.

Consider:
1. Overall sentiment (positive/negative/neutral)
2. Confidence level (0.0-1.0)
3. Potential portfolio impact (-1.0 to 1.0, where positive means good for the stock)
4. Key reasoning

Respond in JSON format:
{
    "sentiment": "positive|negative|neutral",
    "confidence": 0.0-1.0,
    "impact_score": -1.0 to 1.0,
    "analysis": "Brief explanation of sentiment and expected impact",
    "key_factors": ["factor1", "factor2"]
}"""


class SentimentService:
    """Service for analyzing news sentiment using AI."""

    def __init__(self):
        self.client = client

    async def analyze_article(
        self,
        article: Dict[str, Any],
        ticker: str,
    ) -> Optional[Dict[str, Any]]:
        """Analyze sentiment of a single article for a specific ticker."""
        if not self.client:
            return None

        title = article.get("title", "")
        summary = article.get("summary") or article.get("description", "")
        content = f"Title: {title}\nSummary: {summary}"

        try:
            response = await asyncio.to_thread(
                lambda: self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        types.Content(role="user", parts=[types.Part(text=SENTIMENT_PROMPT)]),
                        types.Content(role="user", parts=[types.Part(text=f"Ticker: {ticker}\n\nArticle:\n{content}")]),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        top_p=0.9,
                        max_output_tokens=512,
                        response_mime_type="application/json",
                    ),
                )
            )

            result = json.loads(response.text)
            result["ticker"] = ticker
            result["model_used"] = "gemini-2.0-flash"
            return result

        except Exception as e:
            print(f"Sentiment analysis error for {ticker}: {e}")
            return None

    async def analyze_batch(
        self,
        articles: List[Dict[str, Any]],
        tickers: List[str],
    ) -> List[Dict[str, Any]]:
        """Analyze multiple articles for multiple tickers."""
        # Execute with concurrency limit
        semaphore = asyncio.Semaphore(5)

        async def limited_analyze(article, ticker):
            async with semaphore:
                return await self.analyze_article(article, ticker)

        raw_results = await asyncio.gather(*[
            limited_analyze(article, ticker)
            for article in articles
            for ticker in tickers
            if ticker in article.get("related_tickers", [])
        ], return_exceptions=True)

        # Filter successful results (gather with return_exceptions can yield exceptions)
        return [
            r for r in raw_results
            if isinstance(r, dict) and "sentiment" in r
        ]

    async def store_sentiment(
        self,
        db: AsyncSession,
        article_id: UUID,
        result: Dict[str, Any],
    ) -> SentimentScore:
        """Store sentiment analysis result."""
        sentiment = SentimentScore(
            article_id=article_id,
            ticker=result.get("ticker"),
            sentiment=result.get("sentiment", "neutral"),
            confidence=result.get("confidence", 0.5),
            impact_score=result.get("impact_score", 0.0),
            analysis=result.get("analysis"),
            model_used=result.get("model_used", "gemini-2.0-flash"),
        )
        db.add(sentiment)
        await db.flush()
        return sentiment

    async def process_unanalyzed_articles(
        self,
        db: AsyncSession,
        limit: int = 100,
    ) -> int:
        """Process articles that haven't been analyzed yet."""
        # Get articles without sentiment scores
        result = await db.execute(
            select(NewsArticle)
            .outerjoin(SentimentScore, NewsArticle.id == SentimentScore.article_id)
            .where(SentimentScore.id.is_(None))
            .limit(limit)
        )
        articles = result.scalars().all()

        if not articles:
            return 0

        processed = 0
        for article in articles:
            tickers = article.related_tickers
            if not tickers:
                continue

            for ticker in tickers:
                result = await self.analyze_article({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                }, ticker)

                if result:
                    await self.store_sentiment(db, article.id, result)
                    processed += 1

        await db.commit()
        return processed

    async def get_ticker_sentiment(
        self,
        db: AsyncSession,
        ticker: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get aggregated sentiment for a ticker."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get sentiment scores for ticker
        result = await db.execute(
            select(SentimentScore)
            .join(NewsArticle, SentimentScore.article_id == NewsArticle.id)
            .where(
                and_(
                    SentimentScore.ticker == ticker,
                    NewsArticle.published_at >= datetime.now(timezone.utc) - timedelta(days=days),
                )
            )
        )
        sentiments = result.scalars().all()

        if not sentiments:
            return {
                "ticker": ticker,
                "overall_sentiment": "neutral",
                "avg_confidence": 0.0,
                "avg_impact_score": 0.0,
                "article_count": 0,
                "distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "trend": [],
            }

        # Calculate aggregates
        total = len(sentiments)
        dist = {"positive": 0, "negative": 0, "neutral": 0}
        conf_sum = 0
        impact_sum = 0

        for s in sentiments:
            dist[s.sentiment] = dist.get(s.sentiment, 0) + 1
            conf_sum += float(s.confidence or 0)
            impact_sum += float(s.impact_score or 0)

        # Determine overall sentiment
        overall = max(dist, key=dist.get)

        # Get trend (last 7 days)
        trend_result = await db.execute(
            select(
                func.date(NewsArticle.published_at).label("date"),
                func.avg(SentimentScore.impact_score).label("avg_impact"),
                func.count().label("count"),
            )
            .join(SentimentScore, NewsArticle.id == SentimentScore.article_id)
            .where(
                and_(
                    SentimentScore.ticker == ticker,
                    NewsArticle.published_at >= datetime.now(timezone.utc) - timedelta(days=7),
                )
            )
            .group_by(func.date(NewsArticle.published_at))
            .order_by(func.date(NewsArticle.published_at))
        )
        trend = [
            {"date": row.date.isoformat(), "avg_impact": float(row.avg_impact or 0), "count": row.count}
            for row in trend_result.all()
        ]

        return {
            "ticker": ticker,
            "overall_sentiment": overall,
            "avg_confidence": round(conf_sum / total, 4) if total > 0 else 0,
            "avg_impact_score": round(impact_sum / total, 4) if total > 0 else 0,
            "article_count": total,
            "distribution": dist,
            "trend": trend,
        }

    async def get_portfolio_sentiment(
        self,
        db: AsyncSession,
        portfolio_id: UUID,
        user_id: UUID,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Get sentiment summary for all tickers in a portfolio."""
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)

        from app.models.portfolio import Portfolio
        from app.models.holding import Holding

        result = await db.execute(
            select(Holding.ticker)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        )
        tickers = [row[0] for row in result.all()]

        results = []
        for ticker in tickers:
            sentiment = await self.get_ticker_sentiment(db, ticker, days)
            results.append(sentiment)

        return results


# Global instance
sentiment_service = SentimentService()