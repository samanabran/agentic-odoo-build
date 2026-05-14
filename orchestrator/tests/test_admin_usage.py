from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class _FakeRedis:
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values.get(key)


@pytest.mark.asyncio
async def test_admin_usage_returns_redis_values():
    values = {
        "usage:user:anonymous:tokens:2099-01-01": "1234",
        "usage:tenant:cost:2099-01": "12.5",
    }
    with patch("app.api.admin.time.strftime", side_effect=["2099-01-01", "2099-01"]), patch(
        "app.api.admin.cost_control._get_redis", return_value=_FakeRedis(values)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/admin/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["user_daily_tokens_used"] == 1234
    assert body["tenant_monthly_cost_used_usd"] == 12.5


@pytest.mark.asyncio
async def test_admin_usage_degraded_when_redis_unavailable():
    with patch("app.api.admin.cost_control._get_redis", side_effect=RuntimeError("redis down")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/admin/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["user_daily_tokens_used"] == 0
    assert body["tenant_monthly_cost_used_usd"] == 0.0
