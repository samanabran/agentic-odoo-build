import time

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

_SECRET = "test-gate-secret-key-long-enough-32b"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ORCH_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")


def _token(user_id: int, secret: str = _SECRET, age: int = 0) -> str:
    now = int(time.time()) - age
    return pyjwt.encode({"sub": str(user_id), "iat": now, "exp": now + 300}, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_gate_valid_token_returns_allow():
    from app.main import app

    token = _token(42)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/chat/gate",
            json={"thread_id": 7, "user_id": 42},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "allow"
    assert body["audit_id"] == "gate-7-42"


@pytest.mark.asyncio
async def test_gate_tampered_token_returns_401():
    from app.main import app

    token = _token(42) + "x"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/chat/gate",
            json={"thread_id": 7, "user_id": 42},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gate_expired_token_returns_401():
    from app.main import app

    token = _token(42, age=600)  # minted 10 min ago, 5-min TTL
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/chat/gate",
            json={"thread_id": 7, "user_id": 42},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gate_missing_auth_returns_401():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/chat/gate", json={"thread_id": 7, "user_id": 42})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gate_user_id_mismatch_returns_403():
    from app.main import app

    token = _token(99)  # sub=99 but body claims user_id=42
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/chat/gate",
            json={"thread_id": 7, "user_id": 42},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_gate_non_bearer_scheme_returns_401():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/chat/gate",
            json={"thread_id": 7, "user_id": 42},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
    assert resp.status_code == 401
