"""Alpaca broker integration — connect account, fetch positions, sync to portfolio.

Uses Alpaca's paper-trading API by default (set ALPACA_BASE_URL to change).
Credentials are stored per-user in the broker_connections table.
"""

import base64
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.broker import BrokerConnection


# ── Service ──────────────────────────────────────────────────────────────

_settings = get_settings()


def _enc(plain: str) -> str:
    return base64.b64encode(plain.encode()).decode()


def _dec(blob: str) -> str:
    return base64.b64decode(blob.encode()).decode()


class AlpacaService:
    """Thin async client over the Alpaca Trading API."""

    def __init__(self, base_url: str | None = None, data_url: str | None = None):
        self.base_url = base_url or _settings.alpaca_base_url
        self.data_url = data_url or _settings.alpaca_data_url

    def _headers(self, api_key: str, api_secret: str) -> dict:
        return {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

    async def _request(self, method: str, url: str, api_key: str, api_secret: str) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.request(method, url, headers=self._headers(api_key, api_secret))
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Alpaca unreachable: {e}",
                )
        if resp.status_code in (401, 403):
            # 502, not 401: a downstream credential rejection must not be
            # mistaken by clients for an expired *user* session (the frontend
            # logs out on any 401).
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Alpaca rejected the API credentials — check your API Key ID and Secret Key",
            )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Alpaca resource not found")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise HTTPException(status_code=502, detail=f"Alpaca error: {detail}")
        if resp.status_code == 204 or not resp.text:
            return {}
        return resp.json()

    async def verify_credentials(self, api_key: str, api_secret: str) -> dict:
        """Fetch the account to confirm the keys work. Returns account summary."""
        acct = await self._request("GET", f"{self.base_url}/v2/account", api_key, api_secret)
        return {
            "account_number": acct.get("account_number"),
            "status": acct.get("status"),
            "equity": float(acct.get("equity") or 0),
            "currency": acct.get("currency") or "USD",
        }

    async def get_positions(self, api_key: str, api_secret: str) -> list[dict]:
        """Fetch open positions and map them into PortfolioIQ holding dicts."""
        raw = await self._request("GET", f"{self.base_url}/v2/positions", api_key, api_secret)
        positions = []
        for p in raw:
            qty = float(p.get("qty") or 0)
            avg = float(p.get("avg_entry_price") or 0)
            current = float(p.get("current_price") or avg)
            positions.append(
                {
                    "ticker": p.get("symbol", "").upper(),
                    "quantity": qty,
                    "average_cost": avg,
                    "current_price": current,
                    "currency": "USD",
                }
            )
        return positions


alpaca_service = AlpacaService()


async def get_connection(db: AsyncSession, user_id) -> BrokerConnection | None:
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def connect_alpaca(db: AsyncSession, user_id, api_key: str, api_secret: str) -> dict:
    """Verify credentials against Alpaca, then upsert the stored connection."""
    account = await alpaca_service.verify_credentials(api_key, api_secret)

    existing = await get_connection(db, user_id)
    if existing:
        existing.api_key_enc = _enc(api_key)
        existing.api_secret_enc = _enc(api_secret)
        existing.account_id = account.get("account_number")
        existing.account_status = account.get("status")
        existing.last_sync_at = datetime.now(timezone.utc)
        conn = existing
    else:
        conn = BrokerConnection(
            user_id=user_id,
            broker="alpaca",
            api_key_enc=_enc(api_key),
            api_secret_enc=_enc(api_secret),
            account_id=account.get("account_number"),
            account_status=account.get("status"),
            last_sync_at=datetime.now(timezone.utc),
        )
        db.add(conn)
    await db.flush()
    return {
        "broker": "alpaca",
        "account_number": account.get("account_number"),
        "status": account.get("status"),
        "equity": account.get("equity"),
        "connected_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
    }


async def disconnect_broker(db: AsyncSession, user_id) -> dict:
    existing = await get_connection(db, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No broker connection found")
    await db.delete(existing)
    await db.flush()
    return {"disconnected": True}


async def get_connection_status(db: AsyncSession, user_id) -> dict | None:
    existing = await get_connection(db, user_id)
    if not existing:
        return None
    return {
        "broker": existing.broker,
        "account_number": existing.account_id,
        "status": existing.account_status,
        "last_sync_at": existing.last_sync_at.isoformat() if existing.last_sync_at else None,
    }


async def get_stored_positions(db: AsyncSession, user_id) -> list[dict]:
    """Fetch live positions from Alpaca using the stored credentials."""
    conn = await get_connection(db, user_id)
    if not conn:
        raise HTTPException(
            status_code=400, detail="No broker connected. Connect an Alpaca account first."
        )
    return await alpaca_service.get_positions(_dec(conn.api_key_enc), _dec(conn.api_secret_enc))
