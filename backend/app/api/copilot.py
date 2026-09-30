"""Copilot API endpoints — session management and message handling."""

import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.services.copilot.memory import session_store
from app.services.copilot.streaming import stream_copilot_response, run_copilot_sync

router = APIRouter(prefix="/copilot", tags=["Copilot"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    portfolio_id: Optional[str] = None
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    portfolio_id: Optional[str]
    title: str
    is_active: bool
    message_count: int
    last_message_at: Optional[datetime]
    created_at: datetime


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    response: str
    citations: List[dict]
    tool_calls: List[dict]
    guardrail_flags: List[str]
    needs_gemini_key: bool = False


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: List[dict]


# ── Session Endpoints ────────────────────────────────────────────────────

@router.post("/sessions", response_model=SuccessResponse[SessionResponse])
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Copilot session."""
    session_id = session_store.create_session(
        user_id=str(current_user.id),
        portfolio_id=request.portfolio_id,
        title=request.title,
    )
    
    session = session_store.get_session(session_id)
    return SuccessResponse(data=SessionResponse(**session))


@router.get("/sessions", response_model=SuccessResponse[List[SessionResponse]])
async def list_sessions(
    current_user: User = Depends(get_current_user),
):
    """List all sessions for the current user."""
    sessions = session_store.get_user_sessions(str(current_user.id))
    return SuccessResponse(data=[SessionResponse(**s) for s in sessions])


@router.get("/sessions/{session_id}", response_model=SuccessResponse[SessionResponse])
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a specific session."""
    session = session_store.get_session(session_id)
    if not session or session["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    return SuccessResponse(data=SessionResponse(**session))


@router.delete("/sessions/{session_id}", response_model=SuccessResponse[dict])
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a session."""
    session = session_store.get_session(session_id)
    if not session or session["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_store.delete_session(session_id)
    return SuccessResponse(data={"deleted": True})


# ── Message Endpoints ────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/messages",
    response_model=SuccessResponse[MessageResponse],
)
async def send_message(
    session_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a message to Copilot (synchronous)."""
    session = session_store.get_session(session_id)
    if not session or session["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    result = await run_copilot_sync(
        user_id=str(current_user.id),
        portfolio_id=session.get("portfolio_id"),
        session_id=session_id,
        user_message=request.content,
    )
    
    return SuccessResponse(data=MessageResponse(**result))


@router.get("/gemini-status", response_model=SuccessResponse[dict])
async def copilot_gemini_status(
    current_user: User = Depends(get_current_user),
):
    """Whether the copilot has a Gemini key (user-stored or server env)."""
    from app.services.copilot.gemini_client import resolve_gemini_client
    client, source = await resolve_gemini_client(current_user.id)
    return SuccessResponse(data={"configured": client is not None, "source": source})


@router.post(
    "/sessions/{session_id}/messages/stream",
)
async def stream_message(
    session_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a message to Copilot (streaming SSE)."""
    session = session_store.get_session(session_id)
    if not session or session["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        async for event in stream_copilot_response(
            user_id=str(current_user.id),
            portfolio_id=session.get("portfolio_id"),
            session_id=session_id,
            user_message=request.content,
        ):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=SuccessResponse[SessionMessagesResponse],
)
async def get_messages(
    session_id: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get message history for a session."""
    session = session_store.get_session(session_id)
    if not session or session["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = session_store.get_messages(session_id, limit=limit)
    return SuccessResponse(data=SessionMessagesResponse(session_id=session_id, messages=messages))