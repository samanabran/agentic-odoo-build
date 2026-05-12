# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "ai.origin.mixin"]

    aml_alert_ids = fields.One2many(
        "ai.aml.alert",
        "partner_id",
        string="AML Alerts",
        help="AML alerts linked to this partner.",
    )

    aml_risk_assessment_count = fields.Integer(
        string="AML Risk Assessment Count",
        compute="_compute_aml_risk_assessment_count",
        help="Number of open AML alerts for this partner.",
    )

    @api.depends("aml_alert_ids", "aml_alert_ids.state")
    def _compute_aml_risk_assessment_count(self):
        alert_model = self.env["ai.aml.alert"].sudo()
        for partner in self:
            partner.aml_risk_assessment_count = alert_model.search_count(
                [("partner_id", "=", partner.id), ("state", "!=", "dismissed")]
            )
