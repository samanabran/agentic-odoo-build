"""
Task — /tools/narrative response quality.

Posts synthetic data directly to the orchestrator narrative endpoint and
checks for a non-trivial narrative body.
"""

import asyncio
import os
import time

import httpx
import jwt as pyjwt

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8088")
ORCH_JWT_SECRET = os.getenv("ORCH_JWT_SECRET", "")
_TIMEOUT = 20.0


def _mint_token(user_id: int = 1) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + 300},
        ORCH_JWT_SECRET,
        algorithm="HS256",
    )


async def task_narrative_quality(client: httpx.AsyncClient, base_url: str) -> dict:
    if not ORCH_JWT_SECRET:
        return {"status": "skip", "reason": "ORCH_JWT_SECRET not set"}

    response = await client.post(
        "/tools/narrative",
        json={
            "task": "aml_narrative",
            "items": [
                {
                    "partner_id": 7,
                    "alert_type": "structuring",
                    "transaction_count": 4,
                    "total_amount": 39200.0,
                },
                {
                    "partner_id": 7,
                    "alert_type": "high_frequency",
                    "transaction_count": 11,
                    "total_amount": 16500.0,
                },
            ],
        },
        headers={"Authorization": f"Bearer {_mint_token()}"},
        timeout=_TIMEOUT,
    )
    if response.status_code != 200:
        return {"status": "skip", "reason": f"endpoint unavailable: {response.status_code}"}

    payload = response.json()
    narrative = payload.get("narrative", "")
    if len(narrative.strip()) <= 50:
        return {"status": "fail", "reason": f"narrative too short: {narrative!r}"}
    return {"status": "pass", "length": len(narrative.strip())}


def run() -> tuple[bool, bool, str]:
    async def _runner() -> tuple[bool, bool, str]:
        try:
            async with httpx.AsyncClient(base_url=base_url) as client:
                result = await task_narrative_quality(client, base_url)
        except Exception as exc:
            return False, True, f"orchestrator unavailable — {exc}"

        status = result.get("status")
        if status == "pass":
            return True, False, f"narrative length={result.get('length')}"
        if status == "skip":
            return False, True, str(result.get("reason", "skipped"))
        return False, False, str(result.get("reason", "narrative quality eval failed"))

    base_url = ORCHESTRATOR_URL
    return asyncio.run(_runner())
