"""One-time backfill: attach portfolio tickers to already-stored news articles.

History: `_extract_tickers` used to match only a hard-coded mega-cap list, so
company-news articles fetched for portfolio tickers like AAP / INFY were
stored tagged with substring false-positives (V, T, MA, ...) and never
surfaced in the portfolio feed.

This script, for every distinct holding ticker:
  1. re-fetches that ticker's Finnhub company-news (recent window),
  2. computes each item's deterministic external_id (same as the service),
  3. adds the ticker to related_tickers of any matching stored article.

It also re-derives tags for rows with an empty related_tickers from their
raw_data (Finnhub `related` field + common-token word-boundary match).
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.holding import Holding  # noqa: E402
from app.models.news import NewsArticle  # noqa: E402
from app.services.news.news_service import news_service  # noqa: E402

COMMON_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "JNJ",
    "V", "WMT", "PG", "MA", "T", "VZ", "KO", "PEP", "MRK", "ABT", "COST", "AVGO",
]


async def backfill_company_news_tags(db) -> int:
    """Tag stored articles by matching re-fetched company-news external ids."""
    updated = 0
    tickers = [
        row[0]
        for row in (
            await db.execute(select(Holding.ticker).distinct())
        ).all()
    ]
    print(f"Distinct holding tickers: {tickers}")

    for ticker in tickers:
        articles = await news_service.fetch_finnhub_company_news(ticker, days=30)
        ids = {news_service._generate_external_id("finnhub", a) for a in articles}
        if not ids:
            print(f"  {ticker}: no company news fetched, skipping")
            continue

        result = await db.execute(
            select(NewsArticle).where(
                NewsArticle.source == "finnhub",
                NewsArticle.external_id.in_(ids),
            )
        )
        for article in result.scalars().all():
            tags = set(article.related_tickers or [])
            if ticker not in tags:
                tags.add(ticker)
                article.related_tickers = sorted(tags)
                updated += 1
        print(f"  {ticker}: matched {len(ids)} external ids, updated rows so far: {updated}")

    return updated


async def backfill_empty_rows(db) -> int:
    """Re-derive tags for rows stored with an empty related_tickers list."""
    result = await db.execute(
        select(NewsArticle).where(NewsArticle.related_tickers == [])
    )
    articles = list(result.scalars().all())
    print(f"Articles with empty related_tickers: {len(articles)}")

    updated = 0
    for a in articles:
        raw = a.raw_data or {}
        tickers = set()

        for rel in raw.get("related") or []:
            symbol = rel.get("symbol") if isinstance(rel, dict) else rel
            if symbol:
                tickers.add(str(symbol).upper())

        body = " ".join(
            str(raw.get(k) or "")
            for k in ("title", "summary", "description", "content", "headline")
        ).upper()
        for t in COMMON_TICKERS:
            if t in body and re.search(rf"\b{re.escape(t)}\b", body):
                tickers.add(t)

        if tickers:
            a.related_tickers = sorted(tickers)
            updated += 1

    return updated


async def main() -> None:
    async with async_session_factory() as db:
        n1 = await backfill_company_news_tags(db)
        n2 = await backfill_empty_rows(db)
        await db.commit()
        print(f"Backfill complete: {n1} company-news rows + {n2} empty rows updated.")

        check = await db.execute(
            text(
                "SELECT COUNT(*) FROM news_articles "
                "WHERE related_tickers LIKE '%\"AAP\"%' OR related_tickers LIKE '%\"INFY\"%'"
            )
        )
        print(f"Rows now carrying exact AAP/INFY tokens: {check.scalar()}")


if __name__ == "__main__":
    asyncio.run(main())
