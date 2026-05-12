"""
Task — reconciliation report generation evaluation.

Ensures the finance tool returns an attachment URL under /web/content/.
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


async def _ensure_session(session: httpx.AsyncClient) -> int | None:
    session_ids = await _call_kw(
        session,
        "search",
        "ai.reconciliation.session",
        [[["state", "=", "done"]]],
        {"limit": 1},
    )
    if session_ids:
        return int(session_ids[0])

    statement_ids = await _call_kw(
        session,
        "search",
        "account.bank.statement",
        [[[]]],
        {"limit": 1},
    )
    if not statement_ids:
        return None

    result = await _call_kw(
        session,
        "suggest_bank_reconciliation",
        "ai.brain.finance",
        [int(statement_ids[0])],
    )
    if isinstance(result, dict) and result.get("session_id"):
        return int(result.get("session_id"))
    return None


async def task_finance_report(client: httpx.AsyncClient, base_url: str) -> dict:
    if not ODOO_ADMIN_PASS:
        return {"status": "skip", "reason": "ODOO_ADMIN_PASS not set"}
    if not await _login(client):
        return {"status": "skip", "reason": "admin login failed"}

    session_id = await _ensure_session(client)
    if not session_id:
        return {"status": "skip", "reason": "no reconciliation session available"}

    result = await _call_kw(
        client,
        "generate_reconciliation_report",
        "ai.brain.finance",
        [session_id],
    )
    url = result.get("url") if isinstance(result, dict) else None
    if not url or "/web/content/" not in url:
        return {"status": "fail", "reason": f"unexpected report URL: {result}"}
    return {"status": "pass", "url": url}


def run() -> tuple[bool, bool, str]:
    async def _runner() -> tuple[bool, bool, str]:
        try:
            async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
                result = await task_finance_report(client, base_url)
        except Exception as exc:
            return False, True, f"environment unavailable — {exc}"

        status = result.get("status")
        if status == "pass":
            return True, False, str(result.get("url", "report created"))
        if status == "skip":
            return False, True, str(result.get("reason", "skipped"))
        return False, False, str(result.get("reason", "finance report eval failed"))

    base_url = ODOO_URL
    return asyncio.run(_runner())
