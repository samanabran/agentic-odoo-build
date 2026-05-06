"""
Field redaction layer (E6).

Strips sensitive fields from Odoo record dicts before they leave the
orchestrator for an external LLM provider. Does NOT run for prod-local routes.

Config: /infra/redaction.yaml (path overridden by REDACTION_CONFIG env var).
Full enforcement and nested-field handling implemented in M6.
"""

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger()

_REDACTED = "[REDACTED]"
_config_cache: dict[str, list[str]] | None = None


def _load_config() -> dict[str, list[str]]:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = Path(os.getenv("REDACTION_CONFIG", "/infra/redaction.yaml"))
    if not path.exists():
        logger.warning("redaction_config_not_found", path=str(path))
        _config_cache = {}
        return _config_cache

    with path.open() as fh:
        raw = yaml.safe_load(fh)

    _config_cache = raw.get("redacted_fields", {})
    logger.info("redaction_config_loaded", models=list(_config_cache.keys()))
    return _config_cache


def redact(model_name: str, record: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of *record* with sensitive fields replaced by _REDACTED.
    Dot-notation fields (e.g. 'bank_ids.acc_number') redact the top-level key.
    Full nested traversal implemented in M6.
    """
    config = _load_config()
    sensitive = config.get(model_name, [])
    if not sensitive:
        return record

    result = dict(record)
    for field in sensitive:
        top = field.split(".")[0]
        if top in result:
            result[top] = _REDACTED

    return result


def is_private_route(model_name: str) -> bool:
    """True when the active model is prod-local — redaction is skipped."""
    from app.main import get_active_model
    try:
        return get_active_model() == "prod-local"
    except RuntimeError:
        return False
