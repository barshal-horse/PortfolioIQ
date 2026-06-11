"""Portfolio schemas — create, update, response."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    """Request body to create a portfolio."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    base_currency: str = Field(default="USD", pattern=r"^(USD|INR|EUR|GBP)$")
    benchmark: str = Field(default="SP500", pattern=r"^(NIFTY50|SENSEX|SP500|NASDAQ100)$")


class PortfolioUpdate(BaseModel):
    """Request body to update portfolio metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    benchmark: str | None = Field(
        default=None, pattern=r"^(NIFTY50|SENSEX|SP500|NASDAQ100)$"
    )
    status: str | None = Field(default=None, pattern=r"^(active|archived|draft)$")


class PortfolioSummary(BaseModel):
    """Portfolio list item (lightweight)."""

    id: UUID
    name: str
    status: str
    benchmark: str | None
    base_currency: str
    total_value: float
    total_cost: float
    unrealized_pnl: float
    pnl_percentage: float
    holdings_count: int = 0
    last_analyzed: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SectorAllocation(BaseModel):
    """Sector weight in portfolio."""

    sector: str
    weight: float
    value: float


class PortfolioDetail(PortfolioSummary):
    """Full portfolio with holdings included (from GET /portfolios/{id})."""

    description: str | None = None
    holdings: list["HoldingResponse"] = []
    sector_allocation: list[SectorAllocation] = []


# Avoid circular import — import at bottom
from app.schemas.holding import HoldingResponse  # noqa: E402

PortfolioDetail.model_rebuild()
