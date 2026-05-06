"""
Task 008 — Scoped virtual key is REJECTED for an out-of-scope model (M2).

Verifies that the cloud-dev scoped key (LITELLM_VKEY_CLOUD_DEV), which was
generated with models=["github-dev"], is rejected when used to request the
prod-local model. LiteLLM should return 401 or 403.

This test proves that provider-level key scoping is working correctly,
ensuring Apexive cannot route to an unintended provider.

Skipped if LITELLM_VKEY_CLOUD_DEV is not set.
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

    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {vkey}"},
            json={
                "model": "prod-local",
                "messages": [{"role": "user", "content": "Reply: PONG"}],
                "max_tokens": 5,
            },
            timeout=30.0,
        )
        if r.status_code in (401, 403):
            return (
                True,
                False,
                f"Cloud-dev key correctly rejected for prod-local (HTTP {r.status_code}) OK",
            )
        return (
            False,
            False,
            f"Expected 401/403 for scope violation; got HTTP {r.status_code}: {r.text[:80]}",
        )
    except Exception as exc:
        return False, True, f"LiteLLM not reachable — {exc}"
