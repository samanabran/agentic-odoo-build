import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.middleware import cost_control

router = APIRouter(prefix="/admin", tags=["admin"])


class UsageResponse(BaseModel):
    status: str
    note: str
    date: str
    month: str
    user_id: str
    user_daily_tokens_used: int
    user_daily_tokens_limit: int
    tenant_monthly_cost_used_usd: float
    tenant_monthly_cost_limit_usd: float


@router.get("/usage", response_model=UsageResponse)
async def get_usage() -> UsageResponse:
    """
    Per-user and per-tenant token/cost consumption (D6).
    Reads from Redis counters written by cost_control.record_usage().
    Full implementation in M4 when auth context is wired.
    """
    user_id = "anonymous"
    today = time.strftime("%Y-%m-%d")
    month = time.strftime("%Y-%m")
    day_key = f"usage:user:{user_id}:tokens:{today}"
    month_key = f"usage:tenant:cost:{month}"

    try:
        redis_client = cost_control._get_redis()
        user_daily_tokens_used = int(redis_client.get(day_key) or 0)
        tenant_monthly_cost_used_usd = float(redis_client.get(month_key) or 0.0)
        status = "ok"
        note = "Usage counters loaded from Redis."
    except Exception as exc:
        user_daily_tokens_used = 0
        tenant_monthly_cost_used_usd = 0.0
        status = "degraded"
        note = f"Usage counters unavailable ({exc})."

    return UsageResponse(
        status=status,
        note=note,
        date=today,
        month=month,
        user_id=user_id,
        user_daily_tokens_used=user_daily_tokens_used,
        user_daily_tokens_limit=cost_control.USER_DAILY_BUDGET_TOKENS,
        tenant_monthly_cost_used_usd=round(tenant_monthly_cost_used_usd, 6),
        tenant_monthly_cost_limit_usd=cost_control.TENANT_MONTHLY_BUDGET_USD,
    )
