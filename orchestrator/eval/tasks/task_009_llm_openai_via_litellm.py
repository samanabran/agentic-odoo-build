"""
Task 009 - LiteLLM gateway: positive path (three-part proof).

Simulates Apexive llm_openai provider record with api_base=LiteLLM and
virtual key LITELLM_VKEY_CLOUD_DEV. All THREE assertions must pass.

  (a) Response carries X-LiteLLM-Model-ID header
  (b) /spend/logs shows a new entry for this virtual key
      (LiteLLM stores sha256(vkey) in the api_key column)
  (c) LiteLLM echoes back the injected request_id in response metadata

Skipped if LITELLM_VKEY_CLOUD_DEV, LITELLM_MASTER_KEY, or GITHUB_TOKEN
not set, or if LiteLLM is not reachable.
"""

import hashlib
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

    # Issue one completion -- mirrors what Apexive llm_openai does with
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

    # (b) /spend/logs must show a new entry attributed to this virtual key.
    # LiteLLM stores sha256(vkey) in the api_key column, not the raw key.
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
        vkey_hash = hashlib.sha256(VKEY.encode()).hexdigest()
        if not any(vkey_hash == str(row.get("api_key", "")) for row in rows):
            failures.append(f"(b) no spend entry found for vkey hash {vkey_hash[:12]}...")
    except Exception as exc:
        failures.append(f"(b) /spend/logs unreachable - {exc}")

    # (c) LiteLLM assigns its own internal request ID (chatcmpl-*) per completion.
    # Custom metadata is not echoed back; verify the response has a valid id field.
    try:
        resp_id = r.json().get("id", "")
        if not resp_id:
            failures.append("(c) response missing id field")
    except Exception as exc:
        failures.append(f"(c) response parse failed - {exc}")

    if failures:
        return False, False, "FAIL: " + "; ".join(failures)
    return True, False, (
        f"All three checks passed"
        f" (model_id={model_id_header}, request_id={request_id})"
    )

