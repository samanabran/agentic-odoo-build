# -*- coding: utf-8 -*-
"""ai.conversation — classical extension of llm.thread (ADR 0013, R2).

This module is INTENTIONALLY EMPTY beyond the _inherit declaration.
It is a policy attachment point for later M3 risks:
  - R4 (PR #14): context chip wiring at the controller layer
  - R5 (PR #15): token accounting fields go on mail.message, not here

The CLAUDE.md key-models table refers to "ai.conversation" — this is the
conceptual label, not an Odoo _name. Per ADR 0013 Decision 1, ai.conversation
is llm.thread with ai_brain extensions; no separate ai_conversation table.

If you are tempted to add fields here for "the AI domain", read ADR 0013
first. Most thread-level data already exists on llm.thread (model, res_id,
provider_id, model_id, user_id, tool_ids).
"""
from odoo import fields, models


class AIConversation(models.Model):
    _inherit = "llm.thread"

    is_ai_brain = fields.Boolean(
        string="AI Brain Thread",
        default=False,
        index=True,
        help="True when thread was created via the ai_brain chat surface (ADR 0013 R1). "
             "Routes /llm/thread/generate through the orchestrator policy gate.",
    )
