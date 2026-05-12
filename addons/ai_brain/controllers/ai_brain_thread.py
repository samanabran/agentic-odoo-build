# -*- coding: utf-8 -*-
"""Route intercept for llm.thread generate — ai_brain policy gate (ADR 0013, R1).

AiBrainThreadController overrides /llm/thread/generate for threads created
via the ai_brain surface (is_ai_brain=True).  Non-ai_brain threads are
passed directly to the vendor handler with zero behaviour change.

Fail-open: if the orchestrator gate is unreachable, a warning is logged and
streaming proceeds.  PR #15 will tighten this to fail-closed.
"""
import logging
import os

import requests

from odoo import http
from odoo.http import request

from odoo.addons.llm_thread.controllers.main import LLMThreadController

from .main import _mint_jwt

_logger = logging.getLogger(__name__)


class AiBrainThreadController(LLMThreadController):

    @http.route()
    def llm_thread_generate(self, thread_id: int, **kwargs):
        thread = request.env["llm.thread"].browse(int(thread_id))
        if not thread.exists() or not thread.is_ai_brain:
            return super().llm_thread_generate(thread_id=thread_id, **kwargs)

        try:
            token = _mint_jwt(request.env.user.id)
            orch_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8088")
            resp = requests.post(
                f"{orch_url}/chat/gate",
                json={"thread_id": int(thread_id), "user_id": request.env.user.id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            resp.raise_for_status()
        except Exception as exc:
            _logger.warning("chat_gate_unreachable — fail-open (PR #15 will tighten)", exc_info=exc)

        return super().llm_thread_generate(thread_id=thread_id, **kwargs)
