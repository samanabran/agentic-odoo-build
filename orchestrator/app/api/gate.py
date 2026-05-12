import jwt as pyjwt
import structlog
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.security.jwt import decode_access_token

logger = structlog.get_logger()
router = APIRouter(tags=["gate"])


class GateRequest(BaseModel):
    thread_id: int
    user_id: int


class GateResponse(BaseModel):
    decision: str
    audit_id: str


@router.post("/chat/gate", response_model=GateResponse)
async def chat_gate(
    body: GateRequest,
    authorization: str | None = Header(None),
) -> GateResponse:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
        )

    token = authorization[len("Bearer "):]
    try:
        claims = decode_access_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        token_user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if token_user_id != body.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token subject does not match request user_id",
        )

    audit_id = f"gate-{body.thread_id}-{body.user_id}"
    logger.info("chat_gate_allow", user_id=body.user_id, thread_id=body.thread_id, audit_id=audit_id)
    return GateResponse(decision="allow", audit_id=audit_id)
