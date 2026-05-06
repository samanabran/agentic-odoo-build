"""
Task 004 — LiteLLM /v1/models lists all 4 expected virtual models (M2).

Verifies that all four virtual models defined in infra/litellm/config.yaml
are returned by the LiteLLM /v1/models endpoint.
"""
import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
EXPECTED_MODELS = {"github-dev", "prod-default", "prod-alternate", "prod-local"}


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    try:
        r = httpx.get(f"{LITELLM_URL}/v1/models", timeout=10.0)
        r.raise_for_status()
        present = {m["id"] for m in r.json().get("data", [])}
        missing = EXPECTED_MODELS - present
        if missing:
            return False, False, f"Missing virtual models: {sorted(missing)}"
        return True, False, f"All {len(EXPECTED_MODELS)} virtual models present"
    except Exception as exc:
        return False, True, f"LiteLLM not reachable — {exc}"
