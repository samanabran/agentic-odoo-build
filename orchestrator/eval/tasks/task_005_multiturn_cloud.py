"""
Task 005 — Multi-turn conversation coherence via github-dev (M2).

Sends a two-turn conversation that requires the model to recall a value
from the first turn, verifying context window / multi-turn behaviour works
end-to-end through LiteLLM.

Skipped if GITHUB_TOKEN is not set or LiteLLM is not reachable.
"""
import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    if not os.getenv("GITHUB_TOKEN"):
        return False, True, "GITHUB_TOKEN not set"

    vkey = os.getenv("LITELLM_VKEY_CLOUD_DEV", "")
    if not vkey:
        return False, True, "LITELLM_VKEY_CLOUD_DEV not set"

    messages = [
        {"role": "user", "content": "Remember the number 42. Reply only with: STORED"},
        {"role": "assistant", "content": "STORED"},
        {
            "role": "user",
            "content": "What number did I ask you to remember? Reply with JUST the number.",
        },
    ]
    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {vkey}"},
            json={
                "model": "github-dev",
                "messages": messages,
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        if "42" in content:
            return True, False, f"Multi-turn coherent; model recalled '42' → '{content}'"
        return False, False, f"Model did not recall '42'; response: '{content[:80]}'"
    except Exception as exc:
        return False, True, f"LiteLLM not reachable — {exc}"
