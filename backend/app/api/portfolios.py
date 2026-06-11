"""Portfolio API endpoints — CRUD, CSV upload."""

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessResponse
from app.schemas.holding import CSVUploadResponse, HoldingResponse
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioDetail,
    PortfolioSummary,
    PortfolioUpdate,
)
from app.schemas.market_data import ValuationResponse, ReturnsResponse
from app.services import portfolio_service, market_data_service
from app.utils.csv_parser import parse_holdings_csv

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])
settings = get_settings()


@router.post("", status_code=201, response_model=SuccessResponse[PortfolioSummary])
async def create_portfolio(
    data: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new portfolio."""
    portfolio = await portfolio_service.create_portfolio(db, current_user.id, data)
    summary = PortfolioSummary.model_validate(portfolio)
    summary.holdings_count = 0
    return SuccessResponse(data=summary)


@router.get("", response_model=PaginatedResponse[PortfolioSummary])
async def list_portfolios(
    status: str | None = Query(None, pattern=r"^(active|archived|draft)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all portfolios for the authenticated user."""
    portfolios, total = await portfolio_service.get_portfolios(
        db, current_user.id, status, page, page_size
    )

    items = []
    for p in portfolios:
        summary = PortfolioSummary.model_validate(p)
        summary.holdings_count = getattr(p, "_holdings_count", 0)
        items.append(summary)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            total=total, page=page, page_size=page_size, total_pages=total_pages
        ),
    )


@router.get("/{portfolio_id}", response_model=SuccessResponse[PortfolioDetail])
async def get_portfolio(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a portfolio with all its holdings."""
    portfolio = await portfolio_service.get_portfolio_detail(
        db, portfolio_id, current_user.id
    )

    holdings_responses = []
    for h in portfolio.holdings:
        hr = HoldingResponse(
            id=h.id,
            ticker=h.ticker,
            name=h.instrument.name if h.instrument else h.ticker,
            sector=h.instrument.sector if h.instrument else None,
            quantity=float(h.quantity),
            average_cost=float(h.average_cost),
            current_price=float(h.current_price),
            current_value=float(h.current_value),
            cost_basis=float(h.cost_basis),
            unrealized_pnl=float(h.unrealized_pnl),
            weight=float(h.weight),
            currency=h.currency,
        )
        holdings_responses.append(hr)

    sector_alloc = portfolio_service.get_sector_allocation(portfolio.holdings)

    detail = PortfolioDetail(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        status=portfolio.status,
        benchmark=portfolio.benchmark,
        base_currency=portfolio.base_currency,
        total_value=float(portfolio.total_value),
        total_cost=float(portfolio.total_cost),
        unrealized_pnl=float(portfolio.unrealized_pnl),
        pnl_percentage=float(portfolio.pnl_percentage),
        holdings_count=len(portfolio.holdings),
        last_analyzed=portfolio.last_analyzed,
        created_at=portfolio.created_at,
        holdings=holdings_responses,
        sector_allocation=sector_alloc,
    )

    return SuccessResponse(data=detail)


@router.put("/{portfolio_id}", response_model=SuccessResponse[PortfolioSummary])
async def update_portfolio(
    portfolio_id: UUID,
    data: PortfolioUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update portfolio metadata."""
    portfolio = await portfolio_service.update_portfolio(
        db, portfolio_id, current_user.id, data
    )
    return SuccessResponse(data=PortfolioSummary.model_validate(portfolio))


@router.delete("/{portfolio_id}", status_code=204)
async def delete_portfolio(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a portfolio and all associated data."""
    await portfolio_service.delete_portfolio(db, portfolio_id, current_user.id)


@router.post(
    "/{portfolio_id}/upload-csv",
    status_code=201,
    response_model=SuccessResponse[CSVUploadResponse],
)
async def upload_csv(
    portfolio_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload holdings via CSV file.

    Expected CSV columns: ticker, quantity, average_cost [, currency]
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".csv"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    # Validate file size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    # Parse CSV
    parse_result = parse_holdings_csv(content)

    # Check row limit
    if len(parse_result.holdings) > settings.max_csv_rows:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"Too many rows. Maximum: {settings.max_csv_rows}",
        )

    # If no valid holdings and there are errors, return errors
    if not parse_result.holdings and parse_result.errors:
        return SuccessResponse(
            data=CSVUploadResponse(
                imported=0,
                skipped=parse_result.skipped,
                errors=parse_result.errors,
                holdings=[],
            )
        )

    # Import valid holdings
    import_result = await portfolio_service.bulk_import_holdings(
        db, portfolio_id, current_user.id, parse_result.holdings, mode="merge"
    )

    holdings_responses = []
    for h in import_result["holdings"]:
        hr = HoldingResponse(
            id=h.id,
            ticker=h.ticker,
            name=h.instrument.name if h.instrument else h.ticker,
            sector=h.instrument.sector if h.instrument else None,
            quantity=float(h.quantity),
            average_cost=float(h.average_cost),
            current_price=float(h.current_price),
            current_value=float(h.current_value),
            cost_basis=float(h.cost_basis),
            unrealized_pnl=float(h.unrealized_pnl),
            weight=float(h.weight),
            currency=h.currency,
        )
        holdings_responses.append(hr)

    return SuccessResponse(
        data=CSVUploadResponse(
            imported=import_result["added"] + import_result["updated"],
            skipped=parse_result.skipped,
            errors=parse_result.errors,
            holdings=holdings_responses,
        )
    )


@router.get("/{portfolio_id}/valuation", response_model=SuccessResponse[ValuationResponse])
async def get_portfolio_valuation(
    portfolio_id: UUID,
    period: str = Query("1y", pattern=r"^(1mo|3mo|6mo|1y|3y|5y|max)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio valuation time series (cached, currency converted)."""
    val_series = await market_data_service.get_portfolio_valuation_series(
        db, portfolio_id, current_user.id, period
    )
    return SuccessResponse(data=val_series)


@router.get("/{portfolio_id}/returns", response_model=SuccessResponse[ReturnsResponse])
async def get_portfolio_returns(
    portfolio_id: UUID,
    period: str = Query("1y", pattern=r"^(1mo|3mo|6mo|1y|3y|5y|max)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio daily returns time series."""
    ret_series = await market_data_service.get_portfolio_returns_series(
        db, portfolio_id, current_user.id, period
    )
    return SuccessResponse(data=ret_series)
