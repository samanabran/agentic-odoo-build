# -*- coding: utf-8 -*-
from odoo import fields, models


class AIConversation(models.Model):
    _name = "ai.conversation"
    _description = "AI Conversation"
    _order = "create_date desc"

    name = fields.Char(default="New Conversation")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, index=True)
    res_model = fields.Char()
    res_id = fields.Integer()
