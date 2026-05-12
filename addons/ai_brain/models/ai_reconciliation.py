# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AIReconciliationSession(models.Model):
    _name = "ai.reconciliation.session"
    _inherit = ["ai.origin.mixin", "mail.thread"]
    _description = "AI Reconciliation Session"

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="draft",
    )
    statement_id = fields.Many2one("account.bank.statement")
    tolerance_pct = fields.Float(default=2.0)
    date_range_days = fields.Integer(default=5)
    suggestion_ids = fields.One2many(
        "ai.reconciliation.suggestion",
        "session_id",
    )
    report_attachment_id = fields.Many2one("ir.attachment")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)


class AIReconciliationSuggestion(models.Model):
    _name = "ai.reconciliation.suggestion"
    _description = "AI Reconciliation Suggestion"

    session_id = fields.Many2one("ai.reconciliation.session", required=True)
    statement_line_id = fields.Many2one("account.bank.statement.line")
    move_line_id = fields.Many2one("account.move.line")
    confidence = fields.Integer(help="Confidence score 0-100")
    match_reason = fields.Char()
    llm_rationale = fields.Text()
    state = fields.Selection(
        [
            ("suggested", "Suggested"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="suggested",
    )

    @api.constrains("confidence")
    def _check_confidence(self):
        for rec in self:
            if rec.confidence < 0 or rec.confidence > 100:
                raise ValidationError("Confidence must be between 0 and 100")


class AIAMLAlert(models.Model):
    _name = "ai.aml.alert"
    _inherit = "ai.origin.mixin"
    _description = "AI AML Alert"

    partner_id = fields.Many2one("res.partner")
    alert_type = fields.Selection(
        [
            ("structuring", "Structuring"),
            ("high_frequency", "High Frequency"),
            ("round_number", "Round Number"),
            ("velocity", "Velocity"),
        ]
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ]
    )
    period_start = fields.Date()
    period_end = fields.Date()
    transaction_count = fields.Integer()
    total_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency")
    narrative = fields.Text()
    state = fields.Selection(
        [
            ("open", "Open"),
            ("reviewed", "Reviewed"),
            ("dismissed", "Dismissed"),
        ],
        default="open",
    )
