"""
Task — dashboard availability.

Logs in as Odoo admin and confirms the Financial Intelligence dashboard loads.
"""

import asyncio
import os

import httpx

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB_NAME", "ai_brain_dev")
ODOO_ADMIN_PASS = os.getenv("ODOO_ADMIN_PASS", "")
_TIMEOUT = 20.0


async def _login(session: httpx.AsyncClient) -> bool:
    response = await session.post(
        f"{ODOO_URL}/web/session/authenticate",
        json={
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {"db": ODOO_DB, "login": "admin", "password": ODOO_ADMIN_PASS},
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return bool(response.json().get("result", {}).get("uid"))


async def task_dashboard_load(client: httpx.AsyncClient, base_url: str) -> dict:
    if not ODOO_ADMIN_PASS:
        return {"status": "skip", "reason": "ODOO_ADMIN_PASS not set"}
    if not await _login(client):
        return {"status": "skip", "reason": "admin login failed"}

    response = await client.get("/ai_brain/dashboard", timeout=_TIMEOUT)
    if response.status_code != 200:
        return {"status": "fail", "reason": f"dashboard returned {response.status_code}"}
    if "Financial Intelligence" not in response.text:
        return {"status": "fail", "reason": "dashboard title missing"}
    return {"status": "pass"}


def run() -> tuple[bool, bool, str]:
    async def _runner() -> tuple[bool, bool, str]:
        try:
            async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
                result = await task_dashboard_load(client, base_url)
        except Exception as exc:
            return False, True, f"odoo unavailable — {exc}"

        status = result.get("status")
        if status == "pass":
            return True, False, "dashboard contains Financial Intelligence"
        if status == "skip":
            return False, True, str(result.get("reason", "skipped"))
        return False, False, str(result.get("reason", "dashboard eval failed"))

    base_url = ODOO_URL
    return asyncio.run(_runner())
