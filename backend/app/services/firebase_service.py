"""Firebase ID token verification for Google sign-in.

Verifies Firebase ID tokens issued to the frontend, then upserts the user.
Public keys are fetched from Google's securetoken JWKS endpoint and cached.
"""

import json
import time
from typing import Any
from urllib.request import urlopen

from jose import jwt, JWTError
from fastapi import HTTPException, status

from app.config import get_settings

_settings = get_settings()

_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwks/securetoken@system.gserviceaccount.com"
_JWKS_CACHE_TTL = 3600  # seconds

_jwks_cache: dict | None = None
_jwks_cached_at: float = 0.0


def _get_jwks() -> dict:
    """Fetch (and cache) Google's signing keys for Firebase tokens."""
    global _jwks_cache, _jwks_cached_at
    now = time.time()
    if _jwks_cache is None or (now - _jwks_cached_at) > _JWKS_CACHE_TTL:
        with urlopen(_JWKS_URL, timeout=10) as resp:
            _jwks_cache = json.loads(resp.read().decode())
        _jwks_cached_at = now
    return _jwks_cache


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return its claims (sub, email, name...).

    Raises HTTPException 401 on any validation failure.
    """
    project_id = _settings.firebase_project_id
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server (FIREBASE_PROJECT_ID missing)",
        )

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Malformed authentication token")

    kid = header.get("kid")
    keys = _get_jwks().get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Unknown token signing key")

    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Token has no subject")
    return claims
