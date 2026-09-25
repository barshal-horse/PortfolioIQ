"""FastAPI dependencies — auth, database session injection."""

import os
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_token, get_user_by_id

security = HTTPBearer()

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT from Authorization header, return the User."""
    if TEST_MODE:
        # Return first user or create a test user
        from sqlalchemy import select
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            return user
        # Create a test user if none exists
        test_user = User(
            email="test@portfolioiq.local",
            hashed_password="test",
            full_name="Test User",
            risk_free_rate=0.04,
        )
        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)
        return test_user

    token_data = decode_token(credentials.credentials)
    try:
        user_id = UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
        )
    user = await get_user_by_id(db, user_id)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user
