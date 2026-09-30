"""News scheduler — periodic fetching and processing of financial news."""

import asyncio
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, select

from app.models.news import NewsArticle
from app.models.portfolio import Portfolio
from app.services.news.news_service import news_service
from app.services.news.sentiment_service import sentiment_service
from app.database import get_db


class NewsScheduler:
    """Manages periodic news fetching and sentiment analysis."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self):
        """Start the scheduler with configured jobs."""
        if self._running:
            return

        # Fetch news every 30 minutes during market hours (9:30-16:00 ET, Mon-Fri)
        # Also fetch once at market open and once after close
        self.scheduler.add_job(
            self._fetch_all_portfolios_news,
            CronTrigger(
                hour="9-15",
                minute="0,30",
                day_of_week="mon-fri",
                timezone="America/New_York",
            ),
            id="fetch_portfolio_news",
            max_instances=1,
            coalesce=True,
        )

        # Additional fetch at market open (9:30) and close (16:00)
        self.scheduler.add_job(
            self._fetch_all_portfolios_news,
            CronTrigger(
                hour=9, minute=30,
                day_of_week="mon-fri",
                timezone="America/New_York",
            ),
            id="fetch_market_open",
            max_instances=1,
        )

        self.scheduler.add_job(
            self._fetch_all_portfolios_news,
            CronTrigger(
                hour=16, minute=0,
                day_of_week="mon-fri",
                timezone="America/New_York",
            ),
            id="fetch_market_close",
            max_instances=1,
        )

        # Process sentiment analysis every hour
        self.scheduler.add_job(
            self._process_sentiment_batch,
            IntervalTrigger(hours=1),
            id="process_sentiment",
            max_instances=1,
        )

        # Cleanup old articles daily (keep 90 days)
        self.scheduler.add_job(
            self._cleanup_old_articles,
            CronTrigger(hour=2, minute=0),
            id="cleanup_articles",
            max_instances=1,
        )

        self.scheduler.start()
        self._running = True
        print("News scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            print("News scheduler stopped")

    async def _fetch_all_portfolios_news(self):
        """Fetch news for all active portfolios."""
        try:
            async for db in get_db():
                # Get all active portfolios
                result = await db.execute(
                    select(Portfolio).where(Portfolio.status == "active")
                )
                portfolios = result.scalars().all()

                for portfolio in portfolios:
                    try:
                        result = await news_service.fetch_and_store_portfolio_news(
                            db=db,
                            portfolio_id=portfolio.id,
                            user_id=portfolio.user_id,
                            days=7,
                        )
                        print(
                            f"Fetched news for portfolio {portfolio.id}: "
                            f"{result['stored']} new articles from {result['fetched']} fetched"
                        )
                    except Exception as e:
                        print(f"Error fetching news for portfolio {portfolio.id}: {e}")

                await db.commit()
        except Exception as e:
            print(f"Error in scheduled news fetch: {e}")

    async def _process_sentiment_batch(self):
        """Process unanalyzed articles for sentiment."""
        try:
            async for db in get_db():
                processed = await sentiment_service.process_unanalyzed_articles(db, limit=100)
                if processed > 0:
                    print(f"Processed sentiment for {processed} articles")
        except Exception as e:
            print(f"Error in sentiment processing: {e}")

    async def _cleanup_old_articles(self):
        """Delete articles older than 90 days."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)

            async for db in get_db():
                result = await db.execute(
                    delete(NewsArticle).where(NewsArticle.published_at < cutoff)
                )
                deleted = result.rowcount
                await db.commit()
                if deleted > 0:
                    print(f"Cleaned up {deleted} old news articles")
        except Exception as e:
            print(f"Error cleaning up old articles: {e}")


# Global scheduler instance
news_scheduler = NewsScheduler()


async def init_scheduler():
    """Initialize and start the news scheduler."""
    news_scheduler.start()


async def shutdown_scheduler():
    """Stop the news scheduler."""
    news_scheduler.stop()