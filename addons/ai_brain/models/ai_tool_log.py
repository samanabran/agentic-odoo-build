"""
ai.tool.log — Append-only audit log for AI tool calls (M2 stub).

M2 adds: tool_name, model_used, tokens_in, tokens_out, est_cost_usd, user_id.
M4 extends: args_json, result_json, success, latency_ms, approved_by,
             conversation_id, message_id, origin_ip.
"""
from odoo import fields, models


# Approximate cost coefficients (USD per 1000 tokens). Updated in M4 via ai.policy.
_COST_PER_1K = {
    "github-dev": 0.000165,   # gpt-4o-mini via GitHub Models
    "prod-default": 0.00025,  # claude-haiku
    "prod-alternate": 0.000165,
    "prod-local": 0.0,        # Ollama is free
}


class AiToolLog(models.Model):
    _name = "ai.tool.log"
    _description = "AI Tool Audit Log"
    _order = "create_date desc"
    # Append-only: no write or unlink for non-superuser (enforced via ACL)
    _log_access = True

    tool_name = fields.Char(required=True, index=True)
    model_used = fields.Char(index=True)
    tokens_in = fields.Integer(default=0)
    tokens_out = fields.Integer(default=0)
    est_cost_usd = fields.Float(digits=(10, 6))
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.uid,
        index=True,
    )
    # M4 will add: args_json, result_json, success, latency_ms,
    #              approved_by, conversation_id, message_id, origin_ip

    def _compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        rate = _COST_PER_1K.get(model_name, 0.0)
        return rate * (tokens_in + tokens_out) / 1000.0
