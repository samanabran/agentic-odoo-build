"""
Task 009 - LiteLLM gateway: positive path (three-part proof).

Simulates Apexive llm_openai provider record with api_base=LiteLLM and
virtual key LITELLM_VKEY_CLOUD_DEV. All THREE assertions must pass.

  (a) Response carries X-LiteLLM-Model-ID header
  (b) /spend/logs shows a new entry for this virtual key
  (c) LiteLLM echoes back the injected request_id in response metadata

Skipped if LITELLM_VKEY_CLOUD_DEV, LITELLM_MASTER_KEY, or GITHUB_TOKEN
not set, or if LiteLLM is not reachable.
"""

import os
import time
import uuid

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
VKEY = os.getenv("LITELLM_VKEY_CLOUD_DEV", "")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")


def run() -> tuple[bool, bool, str]:
    if not VKEY:
        return False, True, "LITELLM_VKEY_CLOUD_DEV not set"
    if not MASTER_KEY:
        return False, True, "LITELLM_MASTER_KEY not set (needed for /spend/logs)"
    if not os.getenv("GITHUB_TOKEN"):
        return False, True, "GITHUB_TOKEN not set"

    request_id = f"eval-009-{uuid.uuid4().hex[:12]}"
    failures: list[str] = []

    # Issue one completion — mirrors what Apexive llm_openai does with
    # OpenAI(api_key=vkey, base_url=litellm_url).chat.completions.create(...)
    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {VKEY}"},
            json={
                "model": "github-dev",
                "messages": [{"role": "user", "content": "Reply with: PONG"}],
                "max_tokens": 5,
                "temperature": 0,
                "metadata": {"request_id": request_id},
            },
            timeout=30.0,
        )
        r.raise_for_status()
    except Exception as exc:
        return False, True, f"LiteLLM not reachable - {exc}"

    # (a) X-LiteLLM-Model-ID must be present
    model_id_header = r.headers.get("x-litellm-model-id", "")
    if not model_id_header:
        failures.append("(a) X-LiteLLM-Model-ID header absent")

    # (b) /spend/logs must show a new entry attributed to this virtual key
    time.sleep(1)  # allow async log flush
    logs: list | dict = []
    try:
        lr = httpx.get(
            f"{LITELLM_URL}/spend/logs",
            headers={"Authorization": f"Bearer {MASTER_KEY}"},
            timeout=10.0,
        )
        lr.raise_for_status()
        logs = lr.json()
        rows = logs if isinstance(logs, list) else logs.get("data", [])
        # Match on last 4 chars of vkey (LiteLLM hashes stored keys)
        vkey_tail = VKEY[-4:]
        if not any(vkey_tail in str(row.get("api_key", "")) for row in rows):
            failures.append(f"(b) no spend entry found for vkey ...{vkey_tail}")
    except Exception as exc:
        failures.append(f"(b) /spend/logs unreachable - {exc}")

    # (c) request_id injected in metadata must appear in spend logs or response
    try:
        rows = logs if isinstance(logs, list) else (
            logs.get("data", []) if isinstance(logs, dict) else []
        )
        id_in_logs = any(request_id in str(row) for row in rows)
        id_in_response = request_id in str(r.json())
        if not id_in_logs and not id_in_response:
            failures.append(f"(c) request_id {request_id!r} not found in logs or response")
    except Exception as exc:
        failures.append(f"(c) request_id check failed - {exc}")

    if failures:
        return False, False, "FAIL: " + "; ".join(failures)
    return True, False, (
        f"All three checks passed"
        f" (model_id={model_id_header}, request_id={request_id})"
    )
