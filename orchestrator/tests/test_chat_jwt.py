# -*- coding: utf-8 -*-
"""task_016_chat_jwt_mint_and_validate — JWT plumbing (ADR 0013, R3).

Assertions:
  1. Valid JWT                        → POST /chat 200, reply + user_id returned
  2. Tampered JWT (corrupted payload) → 401
  3. Expired JWT (exp in the past)    → 401
  4. Missing Authorization header     → 401
"""
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security.jwt import mint_access_token


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("ORCH_JWT_SECRET", "test-secret-for-pytest-only")
    monkeypatch.setenv("ENVIRONMENT", "development")


_BODY = {"prompt": "hello", "thread_id": 1}


async def _post(client: AsyncClient, authorization: str | None) -> object:
    headers = {"Authorization": authorization} if authorization is not None else {}
    return await client.post("/chat", json=_BODY, headers=headers)


async def test_valid_jwt_returns_200():
    token = mint_access_token(42)
    with patch("app.api.chat._call_litellm", new=AsyncMock(return_value="pong")):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await _post(client, f"Bearer {token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == 42
    assert body["reply"] == "pong"


async def test_tampered_jwt_returns_401():
    token = mint_access_token(42)
    parts = token.split(".")
    # Corrupt payload segment; signature no longer matches → InvalidTokenError
    tampered = f"{parts[0]}.{parts[1]}TAMPERED.{parts[2]}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(client, f"Bearer {tampered}")
    assert resp.status_code == 401


async def test_expired_jwt_returns_401():
    import jwt as pyjwt

    now = int(time.time())
    expired_token = pyjwt.encode(
        {"sub": "42", "iat": now - 400, "exp": now - 100},
        "test-secret-for-pytest-only",
        algorithm="HS256",
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(client, f"Bearer {expired_token}")
    assert resp.status_code == 401


async def test_missing_authorization_returns_401():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await _post(client, None)
    assert resp.status_code == 401
