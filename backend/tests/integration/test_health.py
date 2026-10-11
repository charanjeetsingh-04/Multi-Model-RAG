"""Integration test — needs a running Postgres + Redis (docker compose)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_liveness_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/health/live")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body


@pytest.mark.asyncio
async def test_problem_json_envelope_on_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/nope")
        assert r.status_code == 404
        body = r.json()
        assert body["code"] == "not_found"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["request_id"]
