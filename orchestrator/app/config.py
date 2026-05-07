import os

import structlog

logger = structlog.get_logger()

_GITHUB_MODEL_PREFIXES = ("github/", "github-")


def get_active_model() -> str:
    """Return the LiteLLM virtual model name for the current environment (D3).

    Routing rules (evaluated in order):
      PRIVATE_MODE=true         -> prod-local
      ENVIRONMENT=production    -> prod-default
      ENVIRONMENT=development   -> github-dev
      anything else             -> RuntimeError
    """
    private_mode = os.getenv("PRIVATE_MODE", "false").lower() == "true"
    environment = os.getenv("ENVIRONMENT", "").lower()

    if private_mode:
        return "prod-local"
    if environment == "production":
        return "prod-default"
    if environment == "development":
        return "github-dev"
    raise RuntimeError(
        f"ENVIRONMENT='{os.getenv('ENVIRONMENT', '')}' is not a recognised value. "
        "Valid values: 'production', 'development'. "
        "Set ENVIRONMENT in your .env file. PRIVATE_MODE=true overrides this check."
    )


def _assert_no_github_models_in_production() -> None:
    """Startup guard (D4, D7): hard-fail if production routes to a GitHub Models endpoint."""
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment != "production":
        return

    default_model = os.getenv("DEFAULT_MODEL", "")
    for prefix in _GITHUB_MODEL_PREFIXES:
        if default_model.lower().startswith(prefix):
            raise RuntimeError(
                f"ENVIRONMENT=production but DEFAULT_MODEL='{default_model}' references a "
                "GitHub Models endpoint. GitHub Models must not serve production traffic — "
                "this violates the Copilot Product Specific Terms and risks account suspension. "
                "Set DEFAULT_MODEL to a licensed provider: openai/*, anthropic/*, or ollama/*."
            )

    if os.getenv("GITHUB_TOKEN"):
        logger.warning(
            "github_token_set_in_production",
            msg="GITHUB_TOKEN is present in production. "
            "It will not be used for LLM routing but should be removed from this environment.",
        )
