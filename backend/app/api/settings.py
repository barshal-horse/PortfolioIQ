"""Settings API — per-user provider API keys (Gemini, etc.)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.services import api_key_service

router = APIRouter(prefix="/settings/api-keys", tags=["Settings"])


class SaveApiKeyRequest(BaseModel):
    provider: str
    key: str


class ApiKeyStatus(BaseModel):
    provider: str
    configured: bool
    source: str  # "user" | "server" | "none"


def _status_for(provider: str, user_key: str | None) -> ApiKeyStatus:
    if user_key:
        return ApiKeyStatus(provider=provider, configured=True, source="user")
    if api_key_service.get_server_gemini_key() if provider == api_key_service.PROVIDER_GEMINI else None:
        return ApiKeyStatus(provider=provider, configured=True, source="server")
    return ApiKeyStatus(provider=provider, configured=False, source="none")


@router.post("", response_model=SuccessResponse[ApiKeyStatus])
async def save_api_key(
    request: SaveApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store a provider API key for the current user (upsert)."""
    if request.provider.strip().lower() != api_key_service.PROVIDER_GEMINI:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")
    ok, err = await api_key_service.validate_gemini_key(request.key)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    try:
        await api_key_service.save_api_key(db, current_user.id, request.provider, request.key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user_key = await api_key_service.get_user_api_key(db, current_user.id, api_key_service.PROVIDER_GEMINI)
    return SuccessResponse(data=_status_for(api_key_service.PROVIDER_GEMINI, user_key))


@router.get("/gemini", response_model=SuccessResponse[ApiKeyStatus])
async def gemini_key_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Whether a Gemini key is configured (user or server level)."""
    user_key = await api_key_service.get_user_api_key(db, current_user.id, api_key_service.PROVIDER_GEMINI)
    return SuccessResponse(data=_status_for(api_key_service.PROVIDER_GEMINI, user_key))


@router.delete("/gemini", response_model=SuccessResponse[dict])
async def delete_gemini_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the user's stored Gemini key."""
    return SuccessResponse(data=await api_key_service.delete_api_key(
        db, current_user.id, api_key_service.PROVIDER_GEMINI
    ))
