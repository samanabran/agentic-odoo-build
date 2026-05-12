"""
Task 003 — LLM round-trip via github-dev (H1).

Sends a deterministic prompt to the github-dev model via the LiteLLM
gateway and asserts the response contains the expected token.

Skipped if GITHUB_TOKEN is not set or if LiteLLM is not reachable.
Counts against the GitHub Models Copilot rate limit (~150-300 req/day).
"""

import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
PROMPT = "Reply with exactly the single word: PONG"
EXPECTED = "PONG"


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    if not os.getenv("GITHUB_TOKEN"):
        return False, True, "GITHUB_TOKEN not set"

    vkey = os.getenv("LITELLM_VKEY_CLOUD_DEV", "")
    if not vkey:
        return False, True, "LITELLM_VKEY_CLOUD_DEV not set"

    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {vkey}"},
            json={
                "model": "github-dev",
                "messages": [{"role": "user", "content": PROMPT}],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        content = (
            r.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if EXPECTED in content.upper():
            return True, False, f"LLM replied via github-dev: '{content.strip()}'"
        return False, False, f"'{EXPECTED}' not found in response: '{content[:80]}'"
    except Exception as exc:
        return False, True, f"LiteLLM not reachable — {exc}"
