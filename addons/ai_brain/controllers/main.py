# -*- coding: utf-8 -*-
"""Odoo HTTP controller for /ai_brain/chat (ADR 0013, R3).

Mints a short-lived HS256 JWT carrying user_id and forwards the chat
request to the orchestrator.  Uses stdlib only (base64, hashlib, hmac)
so no external Python dependency is required in the Odoo container.

The orchestrator validates the JWT with PyJWT.  Both sides produce and
consume standard RFC 7519 HS256 tokens — interoperable by design.
"""
import base64
import hashlib
import hmac
import json
import os
import time

import requests

from odoo import http
from odoo.http import request


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _mint_jwt(user_id: int, ttl: int = 300) -> str:
    """Mint an HS256 JWT with a 5-minute TTL (ADR 0013 R3, CLAUDE.md E1)."""
    secret = os.environ.get("ORCH_JWT_SECRET", "")
    if not secret:
        raise RuntimeError("ORCH_JWT_SECRET is not set — cannot mint orchestrator JWT")
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64url(
        json.dumps({"sub": str(user_id), "iat": now, "exp": now + ttl}).encode()
    )
    signing_input = f"{header}.{payload}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


class AiBrainController(http.Controller):

    @http.route("/ai_brain/chat", type="json", auth="user", methods=["POST"], csrf=False)
    def chat(
        self,
        prompt: str,
        thread_id: int = 0,
        res_model: str = None,
        res_id: int = None,
    ):
        """Receive a chat prompt, mint a JWT, and forward to the orchestrator."""
        user_id = request.env.user.id
        token = _mint_jwt(user_id)

        orch_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000")
        resp = requests.post(
            f"{orch_url}/chat",
            json={
                "prompt": prompt,
                "thread_id": thread_id,
                "res_model": res_model,
                "res_id": res_id,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
