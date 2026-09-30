"""News service — fetching and managing financial news from multiple sources."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.news import NewsArticle, SentimentScore
from app.models.portfolio import Portfolio
from app.models.holding import Holding
from app.utils.ids import to_uuid as _to_uuid


_settings = get_settings()

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
NEWSAPI_BASE_URL = "https://newsapi.org/v2"


class NewsService:
    """Service for fetching and managing financial news."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.finnhub_api_key = _settings.finnhub_api_key
        self.newsapi_api_key = _settings.newsapi_api_key

    async def close(self):
        await self.client.aclose()

    # ── Finnhub Integration ──────────────────────────────────────────────────

    async def fetch_finnhub_company_news(self, ticker: str, days: int = 7) -> List[Dict]:
        """Fetch company-specific news from Finnhub."""
        if not self.finnhub_api_key:
            return []

        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=days)

        params = {
            "symbol": ticker,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "token": self.finnhub_api_key,
        }

        try:
            response = await self.client.get(f"{FINNHUB_BASE_URL}/company-news", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Finnhub company news error for {ticker}: {e}")
            return []

    async def fetch_finnhub_general_news(self, category: str = "general") -> List[Dict]:
        """Fetch general market news from Finnhub."""
        if not self.finnhub_api_key:
            return []

        params = {"category": category, "token": self.finnhub_api_key}

        try:
            response = await self.client.get(f"{FINNHUB_BASE_URL}/news", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Finnhub general news error: {e}")
            return []

    # ── NewsAPI Integration ──────────────────────────────────────────────────

    async def fetch_newsapi_articles(
        self,
        tickers: Optional[List[str]] = None,
        category: Optional[str] = None,
        days: int = 7,
    ) -> List[Dict]:
        """Fetch articles from NewsAPI."""
        if not self.newsapi_api_key:
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        params = {
            "apiKey": self.newsapi_api_key,
            "from": from_date,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 100,
        }

        if tickers:
            params["q"] = " OR ".join(tickers)
        if category:
            params["category"] = category

        try:
            response = await self.client.get(f"{NEWSAPI_BASE_URL}/everything", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
        except Exception as e:
            print(f"NewsAPI error: {e}")
            return []

    # ── Deduplication & Storage ──────────────────────────────────────────────

    def _generate_external_id(self, source: str, article: Dict) -> str:
        """Generate a unique external ID for deduplication."""
        unique_string = f"{source}:{article.get('url', '')}:{article.get('title', '')}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:32]

    def _categorize_article(self, article: Dict, source: str) -> str:
        """Categorize article based on content."""
        title = (article.get("title") or "").lower()
        summary = (article.get("summary") or article.get("description") or "").lower()
        text = f"{title} {summary}"

        earnings_keywords = ["earnings", "quarterly", "revenue", "profit", "eps", "guidance"]
        market_keywords = ["market", "stock", "index", "fed", "rate", "inflation", "economy"]

        if any(k in text for k in earnings_keywords):
            return "earnings"
        elif any(k in text for k in market_keywords):
            return "market"
        return "company"

    async def _store_article(self, db: AsyncSession, article: Dict, source: str) -> Optional[NewsArticle]:
        """Store article if not already exists."""
        external_id = self._generate_external_id(source, article)

        # Check if already exists
        result = await db.execute(
            select(NewsArticle).where(
                and_(
                    NewsArticle.external_id == external_id,
                    NewsArticle.source == source,
                )
            )
        )
        if result.scalar_one_or_none():
            return None  # Already exists

        # Create new article
        news_article = NewsArticle(
            external_id=external_id,
            source=source,
            title=article.get("title", ""),
            summary=article.get("summary") or article.get("description"),
            url=article.get("url", ""),
            image_url=article.get("image_url") or article.get("image"),
            author=article.get("author"),
            published_at=self._parse_date(article.get("publishedAt") or article.get("datetime")),
            category=self._categorize_article(article, source),
            related_tickers=self._extract_tickers(article),
            raw_data=article,
        )
        db.add(news_article)
        await db.flush()
        return news_article

    def _parse_date(self, date_value: Any) -> datetime:
        """Parse various date formats to datetime."""
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, (int, float)):
            return datetime.fromtimestamp(date_value, tz=timezone.utc)
        if isinstance(date_value, str):
            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(date_value, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return datetime.now(timezone.utc)

    def _extract_tickers(self, article: Dict) -> List[str]:
        """Extract ticker symbols from article."""
        # This is a simple extraction - in production, use NLP
        tickers = set()
        text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('description', '')}".upper()

        # Common tickers - in production, match against known tickers
        common_tickers = [
            "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "JNJ",
            "V", "WMT", "PG", "MA", "UNH", "HD", "DIS", "PYPL", "BAC", "ADBE", "NFLX", "CRM",
            "INTC", "CSCO", "PFE", "T", "VZ", "KO", "PEP", "MRK", "ABT", "COST", "AVGO"
        ]

        for ticker in common_tickers:
            if ticker in text:
                tickers.add(ticker)

        return list(tickers)

    # ── Public API ──────────────────────────────────────────────────────────

    async def fetch_and_store_portfolio_news(
        self,
        db: AsyncSession,
        portfolio_id: UUID,
        user_id: UUID,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Fetch news for all tickers in a portfolio and store.

        Accepts an injected database session (from FastAPI dependency or scheduler).
        The caller is responsible for committing.
        """
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)

        # Get portfolio holdings
        result = await db.execute(
            select(Holding.ticker)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        )
        tickers = [row[0] for row in result.all()]

        if not tickers:
            return {"fetched": 0, "stored": 0, "tickers": []}

        stored_count = 0
        fetched_count = 0

        # Fetch from Finnhub (company news)
        for ticker in tickers:
            articles = await self.fetch_finnhub_company_news(ticker, days)
            fetched_count += len(articles)

            for article in articles:
                stored = await self._store_article(db, article, "finnhub")
                if stored:
                    stored_count += 1

        # Fetch general market news from Finnhub
        for category in ["general", "forex", "crypto"]:
            articles = await self.fetch_finnhub_general_news(category)
            fetched_count += len(articles)

            for article in articles:
                stored = await self._store_article(db, article, "finnhub")
                if stored:
                    stored_count += 1

        # Fetch from NewsAPI
        if self.newsapi_api_key:
            articles = await self.fetch_newsapi_articles(tickers, days=days)
            fetched_count += len(articles)

            for article in articles:
                stored = await self._store_article(db, article, "newsapi")
                if stored:
                    stored_count += 1

        await db.commit()
        return {"fetched": fetched_count, "stored": stored_count, "tickers": tickers}

    async def get_portfolio_news(
        self,
        db: AsyncSession,
        portfolio_id: UUID,
        user_id: UUID,
        days: int = 7,
        limit: int = 50,
        offset: int = 0,
    ) -> List[NewsArticle]:
        """Get news articles relevant to a portfolio."""
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)

        # Get portfolio tickers
        result = await db.execute(
            select(Holding.ticker)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        )
        tickers = [row[0] for row in result.all()]

        if not tickers:
            return []

        # Get articles related to portfolio tickers
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Build query for articles with related tickers
        ticker_conditions = [NewsArticle.related_tickers.contains([t]) for t in tickers]

        query = (
            select(NewsArticle)
            .where(
                and_(
                    NewsArticle.published_at >= cutoff_date,
                    or_(*ticker_conditions) if ticker_conditions else False,
                )
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_ticker_news(
        self,
        db: AsyncSession,
        ticker: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsArticle]:
        """Get news for a specific ticker."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(NewsArticle)
            .where(
                and_(
                    NewsArticle.published_at >= cutoff_date,
                    NewsArticle.related_tickers.contains([ticker]),
                )
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_earnings_calendar(
        self,
        db: AsyncSession,
        portfolio_id: UUID,
        user_id: UUID,
        days_ahead: int = 30,
    ) -> List[Dict]:
        """Get upcoming earnings for portfolio holdings."""
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)

        # Get portfolio tickers
        result = await db.execute(
            select(Holding.ticker, Holding.quantity)
            .join(Portfolio, Holding.portfolio_id == Portfolio.id)
            .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        )
        holdings = result.all()

        earnings = []
        for ticker, qty in holdings:
            # In production, fetch from Finnhub earnings calendar
            # For now, return placeholder
            earnings.append({
                "ticker": ticker,
                "quantity": float(qty),
                "earnings_date": None,
                "estimate": None,
                "actual": None,
            })

        return earnings


# Global service instance
news_service = NewsService()