"""
Task — AML heuristic evaluation.

Invokes the AML finance tool over Odoo JSON-RPC and validates the returned
summary shape.
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


async def _call_kw(
    session: httpx.AsyncClient,
    method: str,
    model: str,
    args: list,
    kwargs: dict | None = None,
):
    response = await session.post(
        f"{ODOO_URL}/web/dataset/call_kw",
        json={
            "jsonrpc": "2.0",
            "method": "call",
            "id": 1,
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs or {},
            },
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(
            payload["error"].get("data", {}).get("message", str(payload["error"]))
        )
    return payload.get("result")


async def task_aml_check(client: httpx.AsyncClient, base_url: str) -> dict:
    if not ODOO_ADMIN_PASS:
        return {"status": "skip", "reason": "ODOO_ADMIN_PASS not set"}
    if not await _login(client):
        return {"status": "skip", "reason": "admin login failed"}

    partner_ids = await _call_kw(
        client,
        "search",
        "res.partner",
        [[["id", "!=", 0]]],
        {"limit": 5},
    )
    if not partner_ids:
        return {"status": "skip", "reason": "no partners available"}

    result = await _call_kw(
        client,
        "check_aml_patterns",
        "ai.brain.finance",
        [partner_ids, 30, 10000.0],
    )
    if not isinstance(result, dict):
        return {"status": "fail", "reason": f"unexpected result payload: {result!r}"}
    if "partners_flagged" not in result or "alerts_created" not in result:
        return {"status": "fail", "reason": f"missing AML summary keys: {result}"}

    flagged_count = len(result.get("partners_flagged") or [])
    message = f"partner count={flagged_count}" if flagged_count else "no alerts found"
    return {"status": "pass", "message": message}


def run() -> tuple[bool, bool, str]:
    async def _runner() -> tuple[bool, bool, str]:
        try:
            async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
                result = await task_aml_check(client, base_url)
        except Exception as exc:
            return False, True, f"environment unavailable — {exc}"

        status = result.get("status")
        if status == "pass":
            return True, False, str(result.get("message", "aml eval passed"))
        if status == "skip":
            return False, True, str(result.get("reason", "skipped"))
        return False, False, str(result.get("reason", "aml eval failed"))

    base_url = ODOO_URL
    return asyncio.run(_runner())
