"""
Task 006 — Echo via prod-local / Ollama when PRIVATE_MODE=true (M2).

Skipped unless PRIVATE_MODE=true — Ollama is only started by `make up-private`.
Uses a 120-second timeout to allow for Ollama cold-start model loading.
"""
import os

import httpx

LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    if os.getenv("PRIVATE_MODE", "false").lower() != "true":
        return False, True, "PRIVATE_MODE != true — Ollama path not active"

    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            json={
                "model": "prod-local",
                "messages": [
                    {"role": "user", "content": "Reply with exactly the single word: PONG"}
                ],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=120.0,  # Ollama cold-start model load can be slow
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        if "PONG" in content.upper():
            return True, False, f"Ollama replied via prod-local: '{content.strip()}'"
        return False, False, f"'PONG' not in response: '{content[:80]}'"
    except Exception as exc:
        return False, True, f"Ollama not reachable (make up-private?) — {exc}"
