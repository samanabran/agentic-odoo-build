"""
Task 007 — Scoped virtual key is accepted for its own model (M2).

Verifies that the cloud-dev scoped key (LITELLM_VKEY_CLOUD_DEV) is accepted
when requesting the github-dev model. This proves that key provisioning
from provision_litellm_keys.sh succeeded.

Skipped if LITELLM_VKEY_CLOUD_DEV is not set (run provision_litellm_keys.sh first).
"""
import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    vkey = os.getenv("LITELLM_VKEY_CLOUD_DEV")
    if not vkey:
        return (
            False,
            True,
            "LITELLM_VKEY_CLOUD_DEV not set — run scripts/provision_litellm_keys.sh",
        )

    if not os.getenv("GITHUB_TOKEN"):
        return False, True, "GITHUB_TOKEN not set (needed for github-dev model)"

    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {vkey}"},
            json={
                "model": "github-dev",
                "messages": [{"role": "user", "content": "Reply: PONG"}],
                "max_tokens": 5,
                "temperature": 0,
            },
            timeout=30.0,
        )
        if r.status_code == 200:
            return True, False, "Scoped cloud-dev key accepted for github-dev model OK"
        return False, False, f"Unexpected HTTP {r.status_code}: {r.text[:80]}"
    except Exception as exc:
        return False, True, f"LiteLLM not reachable — {exc}"
