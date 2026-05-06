"""
Token-usage capture for Apexive llm_openai provider (M2).

Overrides _openai_process_non_streaming_response to extract the `usage`
object from the raw OpenAI/LiteLLM response and write a row to ai.tool.log
before the response is returned to the caller.

Design decisions:
- Override target is _openai_process_non_streaming_response (not openai_chat)
  because that is where the raw `response` object is still available before
  it is discarded after content extraction.
- All logging is wrapped in try/except — a logging failure must never break
  the chat flow.
- Streaming responses are not captured in M2 (Apexive uses non-streaming by
  default for assistant threads). M4 will add streaming usage capture.
- Vendor diff remains zero; this override lives entirely in ai_brain.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    def _openai_process_non_streaming_response(self, response):
        """Extend parent to capture token usage into ai.tool.log."""
        result = super()._openai_process_non_streaming_response(response)
        try:
            usage = getattr(response, "usage", None)
            if usage:
                model_name = getattr(response, "model", None) or self.name or ""
                tokens_in = getattr(usage, "prompt_tokens", 0) or 0
                tokens_out = getattr(usage, "completion_tokens", 0) or 0
                log_model = self.env["ai.tool.log"]
                est_cost = log_model._compute_cost(model_name, tokens_in, tokens_out)
                log_model.sudo().create(
                    {
                        "tool_name": "llm.provider.chat",
                        "model_used": model_name,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "est_cost_usd": est_cost,
                        "user_id": self.env.uid,
                    }
                )
        except Exception:
            _logger.exception(
                "ai_brain: failed to write token usage to ai.tool.log — "
                "chat response is unaffected"
            )
        return result
