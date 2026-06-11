"""Tests for auth API endpoints."""

import pytest
from httpx import AsyncClient


class TestAuthRegister:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Successfully register a new user."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
                "base_currency": "USD",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["email"] == "new@example.com"
        assert data["data"]["full_name"] == "New User"
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Reject duplicate email registration."""
        payload = {
            "email": "dupe@example.com",
            "password": "SecurePass123!",
            "full_name": "User One",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Reject passwords shorter than 8 characters."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "short",
                "full_name": "Weak Pass User",
            },
        )
        assert resp.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Reject invalid email formats."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "full_name": "Bad Email User",
            },
        )
        assert resp.status_code == 422


class TestAuthLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Login with valid credentials returns tokens."""
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "SecurePass123!",
                "full_name": "Login User",
            },
        )

        # Login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "login@example.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Reject login with wrong password."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "CorrectPass123!",
                "full_name": "Wrong PW User",
            },
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "WrongPass123!"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Reject login for non-existent email."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "AnyPass123!"},
        )
        assert resp.status_code == 401


class TestAuthProfile:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_get_profile_authenticated(self, registered_client):
        """Authenticated user can view their profile."""
        client, headers, user_id = registered_client
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == "api_test@example.com"

    @pytest.mark.asyncio
    async def test_get_profile_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request is rejected."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401  # No auth header
