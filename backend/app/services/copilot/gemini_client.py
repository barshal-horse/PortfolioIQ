"""Per-request Gemini client resolution.

Priority: user-stored key (api_key_settings) > server env GEMINI_API_KEY.
Called per copilot request so keys saved from the UI take effect
immediately, without a server restart.
"""

from google import genai

from app.config import get_settings
from app.database import async_session_factory
from app.services.api_key_service import resolve_gemini_key


async def resolve_gemini_client(user_id) -> tuple[genai.Client | None, str]:
    """Return (client, source) where source is 'user', 'server', or 'none'."""
    key: str | None = None
    source = "none"

    if user_id:
        try:
            async with async_session_factory() as db:
                key = await resolve_gemini_key(db, user_id)
            if key:
                source = "user"
        except Exception:
            key = None

    if not key:
        key = get_settings().gemini_api_key or None
        if key:
            source = "server"

    return (genai.Client(api_key=key) if key else None), source
