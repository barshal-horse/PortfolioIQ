"""Common response schemas used across all endpoints."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaInfo(BaseModel):
    """Metadata included in every API response."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    request_id: str | None = None


class PaginationMeta(MetaInfo):
    """Metadata for paginated responses."""

    total: int
    page: int
    page_size: int
    total_pages: int


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    status: str = "success"
    data: T
    meta: MetaInfo = Field(default_factory=MetaInfo)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response envelope."""

    status: str = "success"
    data: list[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    """Error detail payload."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    status: str = "error"
    error: ErrorDetail
    meta: MetaInfo = Field(default_factory=MetaInfo)


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
