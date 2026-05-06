"""
Task 011 - LiteLLM invalid virtual key: 401 rejection path.

Sends a chat completion with a syntactically valid but deliberately
wrong virtual key. Verifies:
  (a) LiteLLM returns 401 (not 200, not 500)
  (b) The error body is non-empty (surfaceable to the chat panel)
  (c) No request appears in /spend/logs for this bogus key
      (confirms upstream provider was never reached)

Skipped if LITELLM_MASTER_KEY not set (needed for /spend/logs audit)
or if LiteLLM is not reachable.
"""

import os
import time

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
BOGUS_KEY = "sk-litellm-invalid-key-eval-011-xxxxxxxxxxxx"


def run() -> tuple[bool, bool, str]:
    if not MASTER_KEY:
        return False, True, "LITELLM_MASTER_KEY not set (needed for /spend/logs)"

    failures: list[str] = []

    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {BOGUS_KEY}"},
            json={
                "model": "github-dev",
                "messages": [{"role": "user", "content": "Reply: SHOULD_BE_REJECTED"}],
                "max_tokens": 5,
            },
            timeout=10.0,
        )
    except Exception as exc:
        return False, True, f"LiteLLM not reachable - {exc}"

    # (a) Must be 401
    if r.status_code != 401:
        failures.append(
            f"(a) expected HTTP 401, got {r.status_code}: {r.text[:120]}"
        )

    # (b) Error body must be non-empty and contain a message
    try:
        body = r.json()
        msg = (
            body.get("error", {}).get("message", "")
            or body.get("detail", "")
            or body.get("message", "")
        )
        if not msg:
            failures.append("(b) error body has no surfaceable message field")
    except Exception:
        if not r.text.strip():
            failures.append("(b) response body is empty - nothing to surface to UI")

    # (c) /spend/logs must not contain the bogus key
    time.sleep(1)
    try:
        lr = httpx.get(
            f"{LITELLM_URL}/spend/logs",
            headers={"Authorization": f"Bearer {MASTER_KEY}"},
            timeout=10.0,
        )
        lr.raise_for_status()
        logs = lr.json()
        rows = logs if isinstance(logs, list) else logs.get("data", [])
        bogus_tail = BOGUS_KEY[-8:]
        if any(bogus_tail in str(row.get("api_key", "")) for row in rows):
            failures.append(
                "(c) bogus key found in spend logs - upstream may have been reached"
            )
    except Exception as exc:
        failures.append(f"(c) /spend/logs check failed - {exc}")

    if failures:
        return False, False, "FAIL: " + "; ".join(failures)
    return True, False, "401 rejected cleanly; error surfaceable; no upstream spend logged"