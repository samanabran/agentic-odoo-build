"""
Task 002 — Routing logic (D3).

Unit-tests get_active_model() for the standard development configuration.
Always runnable: no stack, no API keys required.
"""

import os


def run() -> tuple[bool, bool, str]:
    """Return (passed, skipped, message)."""
    # Guarantee a clean environment for this check
    saved = {k: os.environ.get(k) for k in ("ENVIRONMENT", "PRIVATE_MODE")}
    os.environ["ENVIRONMENT"] = "development"
    os.environ["PRIVATE_MODE"] = "false"

    try:
        # Import here so monkeypatched env vars are in effect
        from app.main import get_active_model

        model = get_active_model()
        if model == "github-dev":
            return True, False, f"get_active_model() -> '{model}' OK"
        return False, False, f"expected 'github-dev', got '{model}'"
    except Exception as exc:
        return False, False, f"get_active_model() raised: {exc}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
