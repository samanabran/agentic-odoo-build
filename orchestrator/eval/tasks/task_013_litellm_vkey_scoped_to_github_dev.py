"""
Task 013 - LiteLLM vkey scope enforcement (Constraint 1 of R1).

Verifies that LITELLM_VKEY_CLOUD_DEV is scoped to the github-dev model
only (set by scripts/provision_litellm_keys.sh models:["github-dev"]).

Assertions (both must hold):
  (a) request with model="github-dev" returns 200 + X-LiteLLM-Model-ID
  (b) request with model="prod-local" returns 4xx with "model not
      allowed" (or equivalent) in the error body -- upstream never reached

Skipped if LITELLM_VKEY_CLOUD_DEV not set or LiteLLM not reachable.
"""

import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
VKEY = os.getenv("LITELLM_VKEY_CLOUD_DEV", "")


def _post(model: str) -> httpx.Response:
    return httpx.post(
        f"{LITELLM_URL}/chat/completions",
        headers={"Authorization": f"Bearer {VKEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply: SCOPE_CHECK"}],
            "max_tokens": 5,
        },
        timeout=15.0,
    )


def run() -> tuple[bool, bool, str]:
    if not VKEY:
        return False, True, "LITELLM_VKEY_CLOUD_DEV not set"

    failures: list[str] = []

    # (a) allowed model must succeed
    try:
        ra = _post("github-dev")
    except Exception as exc:
        return False, True, f"LiteLLM not reachable - {exc}"

    if ra.status_code != 200:
        failures.append(
            f"(a) github-dev returned {ra.status_code}, expected 200: {ra.text[:120]}"
        )
    elif not ra.headers.get("x-litellm-model-id", ""):
        failures.append("(a) X-LiteLLM-Model-ID header absent on allowed request")

    # (b) out-of-scope model must be rejected
    try:
        rb = _post("prod-local")
    except Exception as exc:
        failures.append(f"(b) request to prod-local raised exception: {exc}")
        rb = None

    if rb is not None:
        if rb.status_code == 200:
            failures.append(
                "(b) prod-local returned 200 -- scope enforcement broken, "
                "vkey is not restricted to github-dev"
            )
        else:
            body = rb.text.lower()
            if "not allowed" not in body and "unauthorized" not in body and "access" not in body:
                failures.append(
                    f"(b) prod-local rejected ({rb.status_code}) but error body "
                    f"has no 'not allowed' / 'unauthorized': {rb.text[:120]}"
                )

    if failures:
        return False, False, "FAIL: " + "; ".join(failures)
    return True, False, (
        "Scope enforced: github-dev=200+header, prod-local="
        f"{rb.status_code if rb else 'err'}"
    )
