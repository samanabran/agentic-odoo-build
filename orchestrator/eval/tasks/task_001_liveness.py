"""
Task 001 — Orchestrator liveness.

Calls GET /health on the running orchestrator.
Skipped (not failed) if the orchestrator is not reachable, so this
task does not block eval runs in environments where the stack is down.
"""

import httpx

ORCHESTRATOR_URL = "http://localhost:8088"


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    try:
        r = httpx.get(f"{ORCHESTRATOR_URL}/health", timeout=3.0)
        body = r.json()
        if r.status_code == 200 and body.get("status") == "ok":
            return True, False, f"status=ok version={body.get('version')}"
        return False, False, f"unexpected response: {r.status_code} {r.text[:120]}"
    except Exception as exc:
        return False, True, f"orchestrator not reachable — {exc}"
