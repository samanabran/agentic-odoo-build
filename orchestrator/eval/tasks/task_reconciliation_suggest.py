"""
Task — reconciliation suggestion evaluation.

Uses the finance tool directly through Odoo JSON-RPC and verifies a
reconciliation session reaches state=done.
"""

import asyncio
import os

import httpx

from .task_001_liveness import run as run_liveness

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB_NAME", "ai_brain_dev")
ODOO_ADMIN_PASS = os.getenv("ODOO_ADMIN_PASS", "")
_TIMEOUT = 20.0


def _rpc(
    session: httpx.AsyncClient,
    method: str,
    model: str,
    args: list,
    kwargs: dict | None = None,
):
    return session.post(
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
    response = await _rpc(session, method, model, args, kwargs)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(
            payload["error"].get("data", {}).get("message", str(payload["error"]))
        )
    return payload.get("result")


async def task_reconciliation_suggest(client: httpx.AsyncClient, base_url: str) -> dict:
    healthy, skipped, _ = run_liveness()
    if skipped or not healthy:
        return {"status": "skip", "reason": "system not healthy"}
    if not ODOO_ADMIN_PASS:
        return {"status": "skip", "reason": "ODOO_ADMIN_PASS not set"}

    if not await _login(client):
        return {"status": "skip", "reason": "admin login failed"}

    statement_ids = await _call_kw(
        client,
        "search",
        "account.bank.statement",
        [[]],
        {"limit": 1},
    )
    if not statement_ids:
        return {"status": "skip", "reason": "no bank statement available"}

    result = await _call_kw(
        client,
        "suggest_bank_reconciliation",
        "ai.brain.finance",
        [[], int(statement_ids[0])],
    )
    session_id = result.get("session_id") if isinstance(result, dict) else None
    if not session_id:
        return {"status": "fail", "reason": f"missing session_id in result: {result}"}

    session_rows = await _call_kw(
        client,
        "read",
        "ai.reconciliation.session",
        [[session_id], ["state"]],
    )
    state = (session_rows or [{}])[0].get("state")
    if state != "done":
        return {"status": "fail", "reason": f"session {session_id} state={state!r}"}
    return {"status": "pass", "session_id": session_id}


def run() -> tuple[bool, bool, str]:
    async def _runner() -> tuple[bool, bool, str]:
        try:
            async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
                result = await task_reconciliation_suggest(client, base_url)
        except Exception as exc:
            return False, True, f"environment unavailable — {exc}"

        status = result.get("status")
        if status == "pass":
            return True, False, f"session_id={result.get('session_id')} state=done"
        if status == "skip":
            return False, True, str(result.get("reason", "skipped"))
        return False, False, str(result.get("reason", "reconciliation eval failed"))

    base_url = ODOO_URL
    return asyncio.run(_runner())
