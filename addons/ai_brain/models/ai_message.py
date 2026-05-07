# -*- coding: utf-8 -*-
"""ai.message — classical extension of mail.message (ADR 0013, R2).

This module is INTENTIONALLY EMPTY beyond the _inherit declaration.
Policy attachment point for:
  - R5 (PR #15): token_count_input, token_count_output, total_cost_usd
  - any future ai_brain-specific message metadata

The CLAUDE.md key-models table refers to "ai.message" — this is the
conceptual label, not an Odoo _name. Per ADR 0013 Decision 1, ai.message
is mail.message with ai_brain extensions; no separate ai_message table.

Vendor llm/models/mail_message.py already provides:
  - llm_role (Char, indexed, stored, computed from subtype_id)
  - is_error (Boolean, indexed)
  - body_json (Json)
  - role helpers (is_llm_user_message, is_llm_assistant_message, etc.)
  - attachment helpers (_get_image_attachments, _get_pdf_attachments, etc.)

Vendor llm_thread/models/mail_message.py adds:
  - user_vote (Integer)
  - _message_fetch override for llm.thread filtering
  - to_store wiring for llm_role/body_json/user_vote

Do NOT duplicate any of the above.
"""
from odoo import models


class AIMessage(models.Model):
    _inherit = "mail.message"
