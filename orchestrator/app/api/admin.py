from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class UsageResponse(BaseModel):
    status: str
    note: str


@router.get("/usage", response_model=UsageResponse)
async def get_usage() -> UsageResponse:
    """
    Per-user and per-tenant token/cost consumption (D6).
    Reads from Redis counters written by cost_control.record_usage().
    Full implementation in M4 when auth context is wired.
    """
    return UsageResponse(
        status="not_yet_implemented",
        note="Full usage reporting implemented in M4. Redis counters are already being written.",
    )
