"""Auth API endpoints — register, login, refresh, profile."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    TokenRefresh,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.schemas.common import SuccessResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    register_user,
)
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/register", status_code=201, response_model=SuccessResponse[UserResponse])
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    user = await register_user(db, data)
    return SuccessResponse(data=UserResponse.model_validate(user))


@router.post("/login", response_model=SuccessResponse[LoginResponse])
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive access + refresh tokens."""
    user = await authenticate_user(db, data.email, data.password)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return SuccessResponse(
        data=LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
    )


@router.post("/refresh", response_model=SuccessResponse[dict])
async def refresh_token(data: TokenRefresh):
    """Refresh an expired access token."""
    token_data = decode_token(data.refresh_token)
    new_access_token = create_access_token(token_data.sub)

    return SuccessResponse(
        data={
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    )


@router.get("/me", response_model=SuccessResponse[UserResponse])
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get the authenticated user's profile."""
    return SuccessResponse(data=UserResponse.model_validate(current_user))
