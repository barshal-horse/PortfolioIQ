"""Auth schemas — registration, login, tokens."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    base_currency: str = Field(default="USD", pattern=r"^(USD|INR|EUR|GBP)$")


class UserLogin(BaseModel):
    """Request body for login."""

    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Token pair returned on login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user_id
    exp: int


class UserResponse(BaseModel):
    """Public user profile."""

    id: UUID
    email: str
    full_name: str
    base_currency: str
    risk_free_rate: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Full login response including user profile."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
