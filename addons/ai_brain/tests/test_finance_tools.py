# -*- coding: utf-8 -*-
from unittest.mock import patch

import pytest

odoo = pytest.importorskip("odoo")

try:
    from odoo import fields
    from odoo.exceptions import ValidationError
    from odoo.tests.common import TransactionCase
except Exception:
    TransactionCase = None


@pytest.mark.skipif(TransactionCase is None, reason="Odoo ORM not available")
class TestFinanceTools(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance = cls.env["ai.brain.finance"]
        cls.partner = cls.env["res.partner"].create({"name": "AML Partner"})
        journal = cls.env["account.journal"].search([("type", "in", ("bank", "cash"))], limit=1)
        if not journal:
            journal = cls.env["account.journal"].search([], limit=1)
        cls.statement = cls.env["account.bank.statement"].create(
            {
                "name": "AI Finance Test Statement",
                "journal_id": journal.id,
                "date": fields.Date.today(),
            }
        )

    def test_suggest_bank_reconciliation_valid_statement_transitions_and_logs(self):
        before_logs = self.env["ai.tool.log"].search_count([])
        state_history = []
        original_write = type(self.env["ai.reconciliation.session"]).write

        def tracking_write(recordset, vals):
            if "state" in vals:
                state_history.append(vals["state"])
            return original_write(recordset, vals)

        with patch.object(type(self.finance), "_load_unreconciled_statement_lines", autospec=True, return_value=[
            {
                "id": False,
                "amount": 100.0,
                "date": str(fields.Date.today()),
                "partner_id": self.partner.id,
                "ref": "INV 001",
                "currency_id": self.env.company.currency_id.id,
            }
        ]), patch.object(type(self.finance), "_load_open_move_lines", autospec=True, return_value=[
            {
                "id": False,
                "amount": 100.0,
                "date": str(fields.Date.today()),
                "partner_id": self.partner.id,
                "ref": "INV 001",
                "currency_id": self.env.company.currency_id.id,
            }
        ]), patch.object(type(self.finance), "_call_narrative", autospec=True, return_value="Low confidence rationale"), patch.object(type(self.env["ai.reconciliation.session"]), "write", autospec=True, side_effect=tracking_write):
            result = self.finance.suggest_bank_reconciliation(self.statement.id)

        session = self.env["ai.reconciliation.session"].browse(result["session_id"])
        self.assertEqual(session.state, "done")
        self.assertEqual(state_history, ["running", "done"])
        self.assertEqual(result["suggestion_count"], 1)
        self.assertEqual(self.env["ai.tool.log"].search_count([]), before_logs + 1)
        log = self.env["ai.tool.log"].search([], order="id desc", limit=1)
        self.assertEqual(log.tool_name, "suggest_bank_reconciliation")
        self.assertTrue(log.args_sha256)
        self.assertTrue(log.result_sha256)

    def test_suggest_bank_reconciliation_invalid_statement_no_orphan_session(self):
        before_sessions = self.env["ai.reconciliation.session"].search_count([])

        with self.assertRaises(ValidationError):
            self.finance.suggest_bank_reconciliation(999999)

        self.assertEqual(self.env["ai.reconciliation.session"].search_count([]), before_sessions)
        self.assertFalse(
            self.env["ai.reconciliation.session"].search([("state", "=", "running")], limit=1)
        )

    def test_check_aml_patterns_empty_returns_zero_and_logs(self):
        before_logs = self.env["ai.tool.log"].search_count([])

        result = self.finance.check_aml_patterns([], 30)

        self.assertEqual(
            result,
            {"alerts_created": 0, "high_severity": 0, "partners_flagged": []},
        )
        self.assertEqual(self.env["ai.tool.log"].search_count([]), before_logs + 1)

    def test_check_aml_patterns_structuring_creates_alert(self):
        before_logs = self.env["ai.tool.log"].search_count([])
        amounts = [9800.0] * 5
        aml_lines = [
            {
                "id": index + 1,
                "partner_id": self.partner.id,
                "amount": amount,
                "date": fields.Date.today(),
                "timestamp": fields.Datetime.now(),
            }
            for index, amount in enumerate(amounts)
        ]

        with patch.object(type(self.finance), "_load_aml_transactions", autospec=True, return_value=aml_lines), patch.object(type(self.finance), "_call_narrative", autospec=True, return_value="Aggregated AML narrative"):
            result = self.finance.check_aml_patterns([self.partner.id], 30, 10000.0)

        alert = self.env["ai.aml.alert"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("alert_type", "=", "structuring"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertTrue(alert)
        self.assertEqual(alert.severity, "high")
        self.assertEqual(result["alerts_created"], 1)
        self.assertEqual(result["partners_flagged"], [self.partner.id])
        self.assertEqual(self.env["ai.tool.log"].search_count([]), before_logs + 1)

    def test_generate_reconciliation_report_creates_attachment_and_logs(self):
        before_logs = self.env["ai.tool.log"].search_count([])
        session = self.env["ai.reconciliation.session"].create(
            {
                "statement_id": self.statement.id,
                "state": "done",
                "user_id": self.env.user.id,
            }
        )

        result = self.finance.generate_reconciliation_report(session.id)

        attachment = self.env["ir.attachment"].browse(result["attachment_id"])
        self.assertTrue(attachment.exists())
        self.assertEqual(attachment.res_model, "ai.reconciliation.session")
        self.assertEqual(attachment.res_id, session.id)
        self.assertEqual(self.env["ai.tool.log"].search_count([]), before_logs + 1)
        log = self.env["ai.tool.log"].search([], order="id desc", limit=1)
        self.assertEqual(log.tool_name, "generate_reconciliation_report")

    def test_register_hook_registers_three_finance_tools(self):
        self.env["llm.tool"]._register_hook()

        tools = self.env["llm.tool"].search(
            [("decorator_model", "=", "ai.brain.finance")]
        )
        self.assertEqual(len(tools), 3)
