# -*- coding: utf-8 -*-

import datetime
import logging

from odoo import http
from odoo.http import request
from werkzeug.utils import redirect

_logger = logging.getLogger(__name__)


class AiBrainDashboard(http.Controller):

    @staticmethod
    def _login_redirect():
        return redirect("/web/login", code=302)

    @staticmethod
    def _dashboard_redirect():
        return redirect("/ai_brain/dashboard", code=302)

    @staticmethod
    def _forbidden_response():
        return request.make_response("Forbidden", status=403)

    @staticmethod
    def _build_confidence_bars(confidence_dist):
        total = sum(confidence_dist.values()) or 1
        return [
            {
                "label": "95+",
                "count": confidence_dist["95_plus"],
                "width": int((confidence_dist["95_plus"] * 100) / total),
            },
            {
                "label": "80-94",
                "count": confidence_dist["80_94"],
                "width": int((confidence_dist["80_94"] * 100) / total),
            },
            {
                "label": "65-79",
                "count": confidence_dist["65_79"],
                "width": int((confidence_dist["65_79"] * 100) / total),
            },
            {
                "label": "<65",
                "count": confidence_dist["under_65"],
                "width": int((confidence_dist["under_65"] * 100) / total),
            },
        ]

    @http.route("/ai_brain/dashboard", auth="public", type="http")
    def dashboard(self, **kw):
        if not request.session.uid:
            return self._login_redirect()

        session_model = request.env["ai.reconciliation.session"].sudo()
        suggestion_model = request.env["ai.reconciliation.suggestion"].sudo()
        alert_model = request.env["ai.aml.alert"].sudo()

        grouped_sessions = suggestion_model.read_group(
            domain=[("session_id.state", "=", "done")],
            fields=["session_id"],
            groupby=["session_id"],
            lazy=False,
        )
        session_ids = [
            group["session_id"][0]
            for group in grouped_sessions
            if group.get("session_id")
        ]
        sessions = session_model.browse(session_ids)
        sessions = sessions.sorted(key=lambda rec: rec.create_date or rec.write_date or rec.id, reverse=True)

        alerts = alert_model.search([], order="create_date desc", limit=10)
        confidence_dist = {
            "95_plus": suggestion_model.search_count([("confidence", ">=", 95)]),
            "80_94": suggestion_model.search_count([("confidence", ">=", 80), ("confidence", "<", 95)]),
            "65_79": suggestion_model.search_count([("confidence", ">=", 65), ("confidence", "<", 80)]),
            "under_65": suggestion_model.search_count([("confidence", "<", 65)]),
        }

        return request.render(
            "ai_brain.dashboard",
            {
                "sessions": sessions,
                "alerts": alerts,
                "confidence_dist": confidence_dist,
                "confidence_bars": self._build_confidence_bars(confidence_dist),
                "flash_message": request.session.pop("ai_brain_dashboard_flash", None),
                "datetime": datetime,
            },
        )

    @http.route(
        "/ai_brain/reconcile",
        auth="public",
        type="http",
        methods=["POST"],
        csrf=False,
    )
    def reconcile(self, statement_id=None, **kw):
        if not request.session.uid:
            return self._login_redirect()

        csrf_token = kw.get("csrf_token")
        if not csrf_token or csrf_token != request.csrf_token():
            return self._forbidden_response()

        if not statement_id:
            request.session["ai_brain_dashboard_flash"] = {
                "level": "error",
                "message": "Statement ID is required.",
            }
            return self._dashboard_redirect()

        try:
            request.env["ai.brain.finance"].with_user(request.env.user).suggest_bank_reconciliation(
                statement_id=int(statement_id)
            )
            request.session["ai_brain_dashboard_flash"] = {
                "level": "success",
                "message": f"Reconciliation started for statement {int(statement_id)}.",
            }
        except Exception:  # pragma: no cover - defensive UI fallback
            _logger.exception("dashboard_reconcile_failed")
            request.session["ai_brain_dashboard_flash"] = {
                "level": "error",
                "message": f"Unable to run reconciliation for statement {statement_id}.",
            }

        return self._dashboard_redirect()
