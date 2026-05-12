# -*- coding: utf-8 -*-
import pytest

odoo = pytest.importorskip("odoo")

try:
    from odoo.exceptions import ValidationError
    from odoo.tests.common import TransactionCase
except Exception:
    TransactionCase = None


@pytest.mark.skipif(TransactionCase is None, reason="Odoo ORM not available")
class TestReconciliationModels(TransactionCase):

    def test_session_defaults(self):
        session = self.env["ai.reconciliation.session"].create({})

        self.assertEqual(session.state, "draft")
        self.assertEqual(session.user_id, self.env.user)

    def test_confidence_constraint(self):
        session = self.env["ai.reconciliation.session"].create({})

        with self.assertRaises(ValidationError):
            self.env["ai.reconciliation.suggestion"].create(
                {
                    "session_id": session.id,
                    "confidence": 101,
                }
            )

        with self.assertRaises(ValidationError):
            self.env["ai.reconciliation.suggestion"].create(
                {
                    "session_id": session.id,
                    "confidence": -1,
                }
            )

    def test_aml_alert_defaults(self):
        alert = self.env["ai.aml.alert"].create({"severity": "high"})

        self.assertEqual(alert.state, "open")

    def test_ai_origin_fields_present(self):
        session_fields = self.env["ai.reconciliation.session"]._fields
        alert_fields = self.env["ai.aml.alert"]._fields

        for field_name in (
            "x_ai_origin_conversation_id",
            "x_ai_origin_message_id",
            "x_ai_created_at",
        ):
            self.assertIn(field_name, session_fields)
            self.assertIn(field_name, alert_fields)
