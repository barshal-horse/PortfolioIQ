"""Tests for portfolio and holdings API endpoints."""

import pytest
from httpx import AsyncClient


class TestPortfolioCRUD:
    """Tests for portfolio CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_portfolio(self, registered_client):
        """Create a portfolio successfully."""
        client, headers, _ = registered_client
        resp = await client.post(
            "/api/v1/portfolios",
            headers=headers,
            json={
                "name": "Growth Portfolio",
                "description": "Long-term growth",
                "base_currency": "USD",
                "benchmark": "SP500",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Growth Portfolio"
        assert data["status"] == "active"
        assert data["benchmark"] == "SP500"
        assert data["total_value"] == 0.0

    @pytest.mark.asyncio
    async def test_create_duplicate_portfolio(self, registered_client):
        """Reject duplicate portfolio names for same user."""
        client, headers, _ = registered_client
        payload = {"name": "Duplicate Test"}
        await client.post("/api/v1/portfolios", headers=headers, json=payload)
        resp = await client.post("/api/v1/portfolios", headers=headers, json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_portfolios(self, registered_client):
        """List portfolios returns paginated results."""
        client, headers, _ = registered_client
        await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Portfolio A"}
        )
        await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Portfolio B"}
        )

        resp = await client.get("/api/v1/portfolios", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["total"] == 2

    @pytest.mark.asyncio
    async def test_get_portfolio_detail(self, registered_client):
        """Get portfolio with holdings."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Detail Test"}
        )
        pid = create_resp.json()["data"]["id"]

        resp = await client.get(f"/api/v1/portfolios/{pid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "Detail Test"
        assert data["holdings"] == []

    @pytest.mark.asyncio
    async def test_update_portfolio(self, registered_client):
        """Update portfolio metadata."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Update Test"}
        )
        pid = create_resp.json()["data"]["id"]

        resp = await client.put(
            f"/api/v1/portfolios/{pid}",
            headers=headers,
            json={"name": "Updated Name", "benchmark": "NIFTY50"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Name"
        assert resp.json()["data"]["benchmark"] == "NIFTY50"

    @pytest.mark.asyncio
    async def test_delete_portfolio(self, registered_client):
        """Delete a portfolio."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Delete Test"}
        )
        pid = create_resp.json()["data"]["id"]

        resp = await client.delete(f"/api/v1/portfolios/{pid}", headers=headers)
        assert resp.status_code == 204

        # Verify deleted
        resp = await client.get(f"/api/v1/portfolios/{pid}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_portfolio_not_found(self, registered_client):
        """Return 404 for non-existent portfolio."""
        client, headers, _ = registered_client
        import uuid

        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/portfolios/{fake_id}", headers=headers)
        assert resp.status_code == 404


class TestHoldings:
    """Tests for holdings management."""

    @pytest.mark.asyncio
    async def test_add_holding(self, registered_client):
        """Add a holding to a portfolio."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Holdings Test"}
        )
        pid = create_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "AAPL", "quantity": 50, "average_cost": 150.00},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["ticker"] == "AAPL"
        assert data["quantity"] == 50.0
        assert data["average_cost"] == 150.0
        assert data["cost_basis"] == 7500.0

    @pytest.mark.asyncio
    async def test_add_duplicate_holding(self, registered_client):
        """Reject duplicate ticker in same portfolio."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Dupe Hold Test"}
        )
        pid = create_resp.json()["data"]["id"]

        payload = {"ticker": "MSFT", "quantity": 30, "average_cost": 280.00}
        await client.post(
            f"/api/v1/portfolios/{pid}/holdings", headers=headers, json=payload
        )
        resp = await client.post(
            f"/api/v1/portfolios/{pid}/holdings", headers=headers, json=payload
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_holding(self, registered_client):
        """Update a holding's quantity."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Update Hold Test"}
        )
        pid = create_resp.json()["data"]["id"]

        add_resp = await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "GOOGL", "quantity": 20, "average_cost": 140.00},
        )
        hid = add_resp.json()["data"]["id"]

        resp = await client.put(
            f"/api/v1/portfolios/{pid}/holdings/{hid}",
            headers=headers,
            json={"quantity": 35},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["quantity"] == 35.0

    @pytest.mark.asyncio
    async def test_delete_holding(self, registered_client):
        """Delete a holding from a portfolio."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Del Hold Test"}
        )
        pid = create_resp.json()["data"]["id"]

        add_resp = await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "TSLA", "quantity": 10, "average_cost": 250.00},
        )
        hid = add_resp.json()["data"]["id"]

        resp = await client.delete(
            f"/api/v1/portfolios/{pid}/holdings/{hid}", headers=headers
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_portfolio_aggregates_update(self, registered_client):
        """Adding holdings updates portfolio total_value and total_cost."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Aggregates Test"}
        )
        pid = create_resp.json()["data"]["id"]

        # Add two holdings
        await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "AAPL", "quantity": 10, "average_cost": 100.00},
        )
        await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "MSFT", "quantity": 20, "average_cost": 200.00},
        )

        # Check portfolio aggregates
        resp = await client.get(f"/api/v1/portfolios/{pid}", headers=headers)
        data = resp.json()["data"]

        # current_price defaults to average_cost, so:
        # AAPL: 10 * 100 = 1000, MSFT: 20 * 200 = 4000
        assert data["total_value"] == 5000.0
        assert data["total_cost"] == 5000.0
        assert data["unrealized_pnl"] == 0.0
        assert len(data["holdings"]) == 2

    @pytest.mark.asyncio
    async def test_bulk_import_merge(self, registered_client):
        """Bulk import in merge mode adds new and updates existing."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Bulk Test"}
        )
        pid = create_resp.json()["data"]["id"]

        # Add initial holding
        await client.post(
            f"/api/v1/portfolios/{pid}/holdings",
            headers=headers,
            json={"ticker": "AAPL", "quantity": 10, "average_cost": 100.00},
        )

        # Bulk merge: update AAPL, add MSFT
        resp = await client.post(
            f"/api/v1/portfolios/{pid}/holdings/bulk",
            headers=headers,
            json={
                "holdings": [
                    {"ticker": "AAPL", "quantity": 20, "average_cost": 110.00},
                    {"ticker": "MSFT", "quantity": 15, "average_cost": 300.00},
                ],
                "mode": "merge",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["added"] == 1  # MSFT
        assert data["updated"] == 1  # AAPL
        assert len(data["holdings"]) == 2


class TestCSVUpload:
    """Tests for CSV upload endpoint."""

    @pytest.mark.asyncio
    async def test_csv_upload_success(self, registered_client):
        """Upload a valid CSV file."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "CSV Test"}
        )
        pid = create_resp.json()["data"]["id"]

        csv_content = b"ticker,quantity,average_cost\nAAPL,50,150.00\nMSFT,30,280.00"

        resp = await client.post(
            f"/api/v1/portfolios/{pid}/upload-csv",
            headers=headers,
            files={"file": ("portfolio.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["imported"] == 2
        assert data["skipped"] == 0
        assert len(data["holdings"]) == 2

    @pytest.mark.asyncio
    async def test_csv_upload_partial_errors(self, registered_client):
        """CSV with some invalid rows — valid rows imported, errors reported."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Partial CSV"}
        )
        pid = create_resp.json()["data"]["id"]

        csv_content = b"ticker,quantity,average_cost\nAAPL,50,150.00\nBAD!!,-10,abc"

        resp = await client.post(
            f"/api/v1/portfolios/{pid}/upload-csv",
            headers=headers,
            files={"file": ("portfolio.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["imported"] == 1
        assert data["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_csv_upload_wrong_filetype(self, registered_client):
        """Reject non-CSV files."""
        client, headers, _ = registered_client
        create_resp = await client.post(
            "/api/v1/portfolios", headers=headers, json={"name": "Bad File"}
        )
        pid = create_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/portfolios/{pid}/upload-csv",
            headers=headers,
            files={"file": ("data.txt", b"not a csv", "text/plain")},
        )
        assert resp.status_code == 400


class TestHealthCheck:
    """Tests for system health endpoints."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        """Basic health check returns ok."""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
