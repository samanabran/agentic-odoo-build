import os

import httpx
import jwt as pyjwt
import structlog
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_active_model
from app.security.jwt import decode_access_token

logger = structlog.get_logger()
router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str
    thread_id: int
    res_model: str | None = None
    res_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    user_id: int


async def _call_litellm(prompt: str, model: str) -> str:
    """Single LiteLLM call via the LiteLLM proxy — γ-thin scope (ADR 0013 Decision 2)."""
    litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{litellm_url}/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60.0,
        )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    authorization: str | None = Header(None),
) -> ChatResponse:
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

    user_id = int(claims["sub"])
    model = get_active_model()

    logger.info("chat_request", user_id=user_id, model=model, thread_id=body.thread_id)

    reply = await _call_litellm(body.prompt, model)
    return ChatResponse(reply=reply, user_id=user_id)
