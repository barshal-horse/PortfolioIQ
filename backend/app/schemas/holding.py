"""Holding schemas — add, update, bulk import, CSV upload."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    """Request body to add a single holding."""

    ticker: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-^]+$")
    quantity: float = Field(gt=0)
    average_cost: float = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^(USD|INR|EUR|GBP)$")


class HoldingUpdate(BaseModel):
    """Request body to update a holding."""

    quantity: float | None = Field(default=None, gt=0)
    average_cost: float | None = Field(default=None, gt=0)


class HoldingResponse(BaseModel):
    """Holding response with enriched data."""

    id: UUID
    ticker: str
    name: str | None = None
    sector: str | None = None
    quantity: float
    average_cost: float
    current_price: float
    current_value: float
    cost_basis: float
    unrealized_pnl: float
    weight: float
    currency: str

    model_config = {"from_attributes": True}


class BulkHoldingItem(BaseModel):
    """Single item in a bulk holdings request."""

    ticker: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-^]+$")
    quantity: float = Field(gt=0)
    average_cost: float = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^(USD|INR|EUR|GBP)$")


class BulkHoldingsRequest(BaseModel):
    """Request body for bulk holdings import."""

    holdings: list[BulkHoldingItem] = Field(min_length=1, max_length=500)
    mode: Literal["merge", "replace"] = "merge"


class BulkHoldingsResponse(BaseModel):
    """Response from bulk holdings import."""

    added: int
    updated: int
    deleted: int
    holdings: list[HoldingResponse]


class CSVUploadError(BaseModel):
    """A single row error from CSV upload."""

    row: int
    ticker: str | None = None
    error: str


class CSVUploadResponse(BaseModel):
    """Response from CSV upload."""

    imported: int
    skipped: int
    errors: list[CSVUploadError]
    holdings: list[HoldingResponse]
