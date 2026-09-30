"""Market data API endpoints — quote, history, ticker search."""

import asyncio
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.market_data import QuoteResponse, HistoryResponse
from app.services import market_data_service

router = APIRouter(prefix="/market-data", tags=["Market Data"])


class TickerSearchResult(BaseModel):
    """One autocomplete suggestion for the holdings entry form."""

    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None


@router.get("/search", response_model=SuccessResponse[List[TickerSearchResult]])
async def search_tickers(
    q: str = Query(..., min_length=1, max_length=30, description="Company name or ticker fragment"),
    limit: int = Query(8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    """Autocomplete search for tickers by symbol or company name (Yahoo Finance)."""
    results = await asyncio.to_thread(market_data_service.search_tickers_sync, q, limit)
    return SuccessResponse(data=[TickerSearchResult(**r) for r in results])


@router.get("/quote/{ticker}", response_model=SuccessResponse[QuoteResponse])
async def get_ticker_quote(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get real-time quote for a ticker (cached for 15 minutes)."""
    quote = await market_data_service.get_quote(db, ticker)
    return SuccessResponse(data=quote)


@router.get("/history/{ticker}", response_model=SuccessResponse[HistoryResponse])
async def get_ticker_history(
    ticker: str,
    period: str = Query("1y", pattern=r"^(1mo|3mo|6mo|1y|3y|5y|max)$"),
    interval: str = Query("1d", pattern=r"^(1d|1wk|1mo)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get historical daily prices for a ticker."""
    history = await market_data_service.get_history(db, ticker, period, interval)
    return SuccessResponse(data=history)
