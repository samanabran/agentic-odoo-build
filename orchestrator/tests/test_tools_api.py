import time
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security.jwt import mint_access_token


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("ORCH_JWT_SECRET", "test-secret-for-tools-api")
    monkeypatch.setenv("ENVIRONMENT", "development")


async def _post(client: AsyncClient, body: dict, authorization: str | None):
    headers = {"Authorization": authorization} if authorization is not None else {}
    return await client.post("/tools/narrative", json=body, headers=headers)


@pytest.mark.asyncio
async def test_narrative_reconciliation_returns_200():
    token = mint_access_token(42)
    body = {
        "task": "reconciliation_rationale",
        "items": [{"statement_line_id": 1, "move_line_id": 2, "amount": 100.0}],
    }
    with patch(
        "app.api.tools._call_litellm",
        new=AsyncMock(return_value="Likely match due to amount and timing."),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await _post(client, body, f"Bearer {token}")
    assert resp.status_code == 200
    assert resp.json()["narrative"]


@pytest.mark.asyncio
async def test_narrative_aml_empty_items_returns_200():
    token = mint_access_token(7)
    body = {"task": "aml_narrative", "items": []}
    with patch(
        "app.api.tools._call_litellm",
        new=AsyncMock(return_value="No suspicious patterns were supplied for review."),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await _post(client, body, f"Bearer {token}")
    assert resp.status_code == 200
    assert len(resp.json()["narrative"]) > 0


@pytest.mark.asyncio
async def test_narrative_expired_jwt_returns_401():
    now = int(time.time())
    expired_token = pyjwt.encode(
        {"sub": "42", "iat": now - 400, "exp": now - 100},
        "test-secret-for-tools-api",
        algorithm="HS256",
    )
    body = {"task": "aml_narrative", "items": []}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(client, body, f"Bearer {expired_token}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_narrative_missing_authorization_returns_401():
    body = {"task": "aml_narrative", "items": []}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(client, body, None)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_narrative_unknown_task_returns_422():
    token = mint_access_token(42)
    body = {"task": "unknown_task", "items": []}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post(client, body, f"Bearer {token}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tools_endpoint_appears_in_openapi():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/tools/narrative" in resp.json()["paths"]
