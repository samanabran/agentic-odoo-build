# -*- coding: utf-8 -*-

from odoo.http import Request
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install")
class TestDashboardController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "AML Test Partner"})

    def setUp(self):
        super().setUp()
        self.env["ai.aml.alert"].search([]).unlink()
        self.env["ai.reconciliation.suggestion"].search([]).unlink()
        self.env["ai.reconciliation.session"].search([]).unlink()

    def test_authenticated_get_returns_html(self):
        self.authenticate("admin", "admin")

        response = self.url_open("/ai_brain/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("Content-Type", ""))
        self.assertIn("Financial Intelligence", response.text)

    def test_unauthenticated_get_redirects_to_login(self):
        response = self.url_open("/ai_brain/dashboard", allow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/web/login", response.headers.get("Location", ""))

    def test_zero_aml_alerts_message_present(self):
        self.authenticate("admin", "admin")

        response = self.url_open("/ai_brain/dashboard")

        self.assertIn("No active alerts", response.text)

    def test_high_severity_alert_badge_present(self):
        self.env["ai.aml.alert"].create(
            {
                "partner_id": self.partner.id,
                "alert_type": "structuring",
                "severity": "high",
                "narrative": "Potential structuring activity detected.",
            }
        )
        self.authenticate("admin", "admin")

        response = self.url_open("/ai_brain/dashboard")

        self.assertIn("badge-high", response.text)
        self.assertIn("Potential structuring activity detected.", response.text)

    def test_post_without_csrf_returns_403(self):
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/ai_brain/reconcile",
            data={"statement_id": "1"},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 403)

    def test_post_with_csrf_handles_redirect_to_dashboard(self):
        self.authenticate("admin", "admin")
        csrf_token = Request.csrf_token(self)

        response = self.url_open(
            "/ai_brain/reconcile",
            data={"statement_id": "1", "csrf_token": csrf_token},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/ai_brain/dashboard")
