import os
import time

import jwt as pyjwt

_ALGORITHM = "HS256"
_TTL_SECONDS = 300  # 5-minute TTL per ADR 0013 R3


def _secret() -> str:
    secret = os.getenv("ORCH_JWT_SECRET")
    if not secret:
        raise RuntimeError("ORCH_JWT_SECRET environment variable is not set")
    return secret


def mint_access_token(user_id: int) -> str:
    """Mint a short-lived JWT carrying user_id (ADR 0013 R3)."""
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + _TTL_SECONDS}
    return pyjwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises pyjwt.ExpiredSignatureError or pyjwt.InvalidTokenError."""
    return pyjwt.decode(token, _secret(), algorithms=[_ALGORITHM])
