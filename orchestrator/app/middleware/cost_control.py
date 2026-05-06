"""
Cost control middleware (D6).

Tracks per-user daily token budgets and per-tenant monthly USD budgets in Redis.
Enforcement (refusing requests when budgets are exceeded) is wired into the
request context in M4 once authentication is available.
"""

import os
import time
from typing import Optional

import structlog

logger = structlog.get_logger()

USER_DAILY_BUDGET_TOKENS: int = int(os.getenv("USER_DAILY_BUDGET_TOKENS", "50000"))
TENANT_MONTHLY_BUDGET_USD: float = float(os.getenv("TENANT_MONTHLY_BUDGET_USD", "200.0"))
TENANT_WARN_THRESHOLD: float = 0.80  # warn at 80% consumption

_redis_client: Optional[object] = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(
            os.getenv("ORCH_REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
    return _redis_client


def record_usage(
    user_id: str,
    tokens_in: int,
    tokens_out: int,
    model: str,
    est_cost_usd: float = 0.0,
) -> None:
    """
    Record token and cost usage for a user. Safe to call without a running
    Redis (logs a warning and continues).
    """
    try:
        r = _get_redis()
        day_key = f"usage:user:{user_id}:tokens:{_today()}"
        r.incrby(day_key, tokens_in + tokens_out)
        r.expire(day_key, 86400 * 2)

        month_key = f"usage:tenant:cost:{_month()}"
        r.incrbyfloat(month_key, est_cost_usd)
        r.expire(month_key, 86400 * 35)

        logger.info(
            "usage_recorded",
            user_id=user_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            est_cost_usd=round(est_cost_usd, 6),
        )
    except Exception as exc:
        logger.warning("usage_record_failed", error=str(exc))


def check_user_budget(user_id: str) -> tuple[bool, str]:
    """
    Return (allowed, reason).

    M1: tracking only — always returns (True, "ok").
    Enforcement enabled in M4.
    """
    try:
        r = _get_redis()
        day_key = f"usage:user:{user_id}:tokens:{_today()}"
        used = int(r.get(day_key) or 0)
        if used >= USER_DAILY_BUDGET_TOKENS:
            logger.warning(
                "user_daily_budget_exceeded",
                user_id=user_id,
                used=used,
                limit=USER_DAILY_BUDGET_TOKENS,
            )
        return True, "ok"  # enforcement active from M4
    except Exception as exc:
        logger.warning("budget_check_failed", error=str(exc))
        return True, "ok"


def check_tenant_budget() -> tuple[bool, str]:
    """
    Return (allowed, reason).

    Logs a warning at 80% and would block at 100%. M1: always returns (True, "ok").
    """
    try:
        r = _get_redis()
        month_key = f"usage:tenant:cost:{_month()}"
        spent = float(r.get(month_key) or 0.0)
        ratio = spent / TENANT_MONTHLY_BUDGET_USD if TENANT_MONTHLY_BUDGET_USD > 0 else 0.0
        if ratio >= 1.0:
            logger.error(
                "tenant_monthly_budget_exceeded",
                spent=round(spent, 4),
                limit=TENANT_MONTHLY_BUDGET_USD,
            )
        elif ratio >= TENANT_WARN_THRESHOLD:
            logger.warning(
                "tenant_monthly_budget_warning",
                spent=round(spent, 4),
                limit=TENANT_MONTHLY_BUDGET_USD,
                pct=round(ratio * 100, 1),
            )
        return True, "ok"  # enforcement active from M4
    except Exception as exc:
        logger.warning("tenant_budget_check_failed", error=str(exc))
        return True, "ok"


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _month() -> str:
    return time.strftime("%Y-%m")
