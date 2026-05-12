# -*- coding: utf-8 -*-
"""Tests for AiBrainThreadController route intercept (ADR 0013, R1)."""
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("odoo")
from odoo.tests.common import TransactionCase


class TestRouteIntercept(TransactionCase):

    def _make_controller(self):
        from odoo.addons.ai_brain.controllers.ai_brain_thread import AiBrainThreadController
        return AiBrainThreadController()

    def _mock_request(self, user_id=1):
        mock_req = MagicMock()
        mock_req.env = self.env
        mock_req.env.user = MagicMock()
        mock_req.env.user.id = user_id
        return mock_req

    def test_non_ai_brain_thread_bypasses_gate(self):
        """Threads with is_ai_brain=False go directly to super() — gate never called."""
        thread = self.env["llm.thread"].create({})
        self.assertFalse(thread.is_ai_brain)

        ctrl = self._make_controller()
        with (
            patch("odoo.http.request", self._mock_request()),
            patch(
                "odoo.addons.llm_thread.controllers.main.LLMThreadController.llm_thread_generate",
                return_value="ok",
            ) as mock_super,
            patch("requests.post") as mock_post,
        ):
            result = ctrl.llm_thread_generate(thread_id=thread.id)

        mock_post.assert_not_called()
        mock_super.assert_called_once()
        self.assertEqual(result, "ok")

    def test_ai_brain_thread_calls_gate_then_super(self):
        """Threads with is_ai_brain=True call the gate before streaming."""
        thread = self.env["llm.thread"].create({"is_ai_brain": True})

        ctrl = self._make_controller()
        mock_gate_resp = MagicMock()
        mock_gate_resp.raise_for_status = MagicMock()

        with (
            patch("odoo.http.request", self._mock_request()),
            patch(
                "odoo.addons.ai_brain.controllers.ai_brain_thread._mint_jwt",
                return_value="test.jwt.token",
            ),
            patch("requests.post", return_value=mock_gate_resp) as mock_post,
            patch(
                "odoo.addons.llm_thread.controllers.main.LLMThreadController.llm_thread_generate",
                return_value="streamed",
            ) as mock_super,
        ):
            result = ctrl.llm_thread_generate(thread_id=thread.id)

        mock_post.assert_called_once()
        url_called = mock_post.call_args[0][0]
        self.assertIn("/chat/gate", url_called)
        mock_super.assert_called_once()
        self.assertEqual(result, "streamed")
