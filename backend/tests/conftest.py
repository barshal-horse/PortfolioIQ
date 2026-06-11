"""Shared test fixtures — in-memory SQLite async database, test client, auth helpers."""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models import Base
from app.services.auth_service import create_access_token, hash_password
from app.models.user import User

# ── Async SQLite engine for tests (no PostgreSQL needed) ─────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override FastAPI's get_db dependency to use test database."""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Override the database dependency
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for service-level tests."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for API-level tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        base_currency="USD",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Generate Authorization header for the test user."""
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def registered_client(client: AsyncClient) -> tuple[AsyncClient, dict, str]:
    """Register a user via API and return (client, auth_headers, user_id)."""
    # Register
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "api_test@example.com",
            "password": "ApiTestPass123!",
            "full_name": "API Test User",
            "base_currency": "USD",
        },
    )
    assert register_resp.status_code == 201

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "api_test@example.com",
            "password": "ApiTestPass123!",
        },
    )
    assert login_resp.status_code == 200
    data = login_resp.json()["data"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    user_id = data["user"]["id"]

    return client, headers, user_id
