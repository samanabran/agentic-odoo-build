# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, time as dt_time, timedelta

import httpx

from odoo import _, fields, models
from odoo.http import request as http_request
from odoo.addons.llm_tool.decorators import llm_tool
from odoo.exceptions import ValidationError

from ..services.matching_engine import MatchingEngine


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _mint_orchestrator_jwt(user_id: int, ttl: int = 300) -> str:
    secret = os.environ.get("ORCH_JWT_SECRET", "")
    if not secret:
        raise RuntimeError("ORCH_JWT_SECRET is not set — cannot mint orchestrator JWT")
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64url(
        json.dumps({"sub": str(user_id), "iat": now, "exp": now + ttl}).encode()
    )
    signing_input = f"{header}.{payload}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


class AiBrainFinance(models.Model):
    _name = "ai.brain.finance"
    _description = "AI Brain Finance Tools"
    _inherit = ["mail.thread"]

    @llm_tool(requires_user_consent=True, read_only_hint=False)
    def suggest_bank_reconciliation(
        self,
        statement_id: int,
        tolerance_pct: float = 2.0,
        date_range_days: int = 5,
    ) -> dict:
        """Suggest candidate bank reconciliation matches for a statement."""
        started_at = time.perf_counter()
        audit_context = self._get_audit_context()
        args = {
            "statement_id": statement_id,
            "tolerance_pct": tolerance_pct,
            "date_range_days": date_range_days,
        }
        session = self.env["ai.reconciliation.session"]
        result = {}
        try:
            statement = self._get_statement(statement_id)
            session = self.env["ai.reconciliation.session"].create(
                {
                    "statement_id": statement.id,
                    "tolerance_pct": tolerance_pct,
                    "date_range_days": date_range_days,
                    "user_id": self.env.user.id,
                    "x_ai_origin_conversation_id": audit_context["conversation_id"],
                    "x_ai_origin_message_id": audit_context["message_id"],
                    "x_ai_created_at": fields.Datetime.now(),
                }
            )
            session.write({"state": "running"})

            stmt_lines = self._load_unreconciled_statement_lines(statement)
            move_lines = self._load_open_move_lines(statement)
            engine = MatchingEngine(
                tolerance_pct=tolerance_pct,
                date_range_days=date_range_days,
            )
            candidates = engine.find_candidates(
                {
                    "statement_id": statement.id,
                    "tolerance_pct": tolerance_pct,
                    "date_range_days": date_range_days,
                },
                stmt_lines,
                move_lines,
            )

            suggestion_vals = [
                {
                    "session_id": session.id,
                    "statement_line_id": candidate["stmt_line_id"],
                    "move_line_id": candidate["move_line_id"],
                    "confidence": candidate["confidence"],
                    "match_reason": candidate["match_reason"],
                }
                for candidate in candidates
            ]
            suggestions = (
                self.env["ai.reconciliation.suggestion"].create(suggestion_vals)
                if suggestion_vals
                else self.env["ai.reconciliation.suggestion"]
            )
            low_conf_suggestions = suggestions.filtered(lambda rec: rec.confidence < 65)
            if low_conf_suggestions:
                narrative_items = [
                    {
                        "statement_line_id": rec.statement_line_id.id,
                        "move_line_id": rec.move_line_id.id,
                        "confidence": rec.confidence,
                        "match_reason": rec.match_reason,
                    }
                    for rec in low_conf_suggestions
                ]
                narrative = self._call_narrative(
                    task="reconciliation_rationale",
                    items=narrative_items,
                )
                low_conf_suggestions.write({"llm_rationale": narrative})

            session.write({"state": "done"})
            high_confidence = len(suggestions.filtered(lambda rec: rec.confidence >= 65))
            manual_review = len(low_conf_suggestions)
            result = {
                "session_id": session.id,
                "suggestion_count": len(suggestions),
                "high_confidence": high_confidence,
                "manual_review": manual_review,
            }
            self._log_tool_call(
                tool_name="suggest_bank_reconciliation",
                args=args,
                result=result,
                success=True,
                latency_ms=self._elapsed_ms(started_at),
                model_used="orchestrator:/tools/narrative",
                audit_context=audit_context,
            )
            return result
        except Exception as exc:
            if session:
                session.write({"state": "error"})
            self._log_tool_call(
                tool_name="suggest_bank_reconciliation",
                args=args,
                result={"error": str(exc)},
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                model_used="orchestrator:/tools/narrative",
                audit_context=audit_context,
            )
            raise

    @llm_tool(requires_user_consent=True, read_only_hint=False)
    def generate_reconciliation_report(self, session_id: int) -> dict:
        """Generate an HTML reconciliation report attachment for a session."""
        started_at = time.perf_counter()
        audit_context = self._get_audit_context()
        args = {"session_id": session_id}
        try:
            session = self.env["ai.reconciliation.session"].browse(session_id)
            if not session.exists():
                raise ValueError(_("Reconciliation session not found"))

            html = self._render_reconciliation_report_html(session)
            attachment = self.env["ir.attachment"].create(
                {
                    "name": f"reconciliation-report-{session.id}.html",
                    "type": "binary",
                    "mimetype": "text/html",
                    "datas": base64.b64encode(html.encode()),
                    "res_model": "ai.reconciliation.session",
                    "res_id": session.id,
                }
            )
            session.write({"report_attachment_id": attachment.id})
            result = {
                "url": f"/web/content/{attachment.id}",
                "attachment_id": attachment.id,
            }
            self._log_tool_call(
                tool_name="generate_reconciliation_report",
                args=args,
                result=result,
                success=True,
                latency_ms=self._elapsed_ms(started_at),
                model_used="local:ir.attachment",
                audit_context=audit_context,
            )
            return result
        except Exception as exc:
            self._log_tool_call(
                tool_name="generate_reconciliation_report",
                args=args,
                result={"error": str(exc)},
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                model_used="local:ir.attachment",
                audit_context=audit_context,
            )
            raise

    @llm_tool(requires_user_consent=True, read_only_hint=False)
    def check_aml_patterns(
        self,
        partner_ids: list[int],
        period_days: int = 30,
        threshold_currency: float = 10000.0,
    ) -> dict:
        """Check partners for simple AML warning patterns."""
        started_at = time.perf_counter()
        audit_context = self._get_audit_context()
        args = {
            "partner_ids": partner_ids,
            "period_days": period_days,
            "threshold_currency": threshold_currency,
        }
        try:
            if not partner_ids:
                result = {
                    "alerts_created": 0,
                    "high_severity": 0,
                    "partners_flagged": [],
                }
                self._log_tool_call(
                    tool_name="check_aml_patterns",
                    args=args,
                    result=result,
                    success=True,
                    latency_ms=self._elapsed_ms(started_at),
                    model_used="orchestrator:/tools/narrative",
                    audit_context=audit_context,
                )
                return result

            transactions = self._load_aml_transactions(partner_ids, period_days)
            alerts_to_create = []
            summary_items = []

            for partner_id in partner_ids:
                partner_lines = [tx for tx in transactions if tx["partner_id"] == partner_id]
                structuring = self._detect_structuring(partner_lines, threshold_currency)
                if structuring:
                    alerts_to_create.append(
                        self._build_aml_alert_vals(
                            partner_id=partner_id,
                            alert_type="structuring",
                            severity="high",
                            period_days=period_days,
                            transaction_count=structuring["transaction_count"],
                            total_amount=structuring["total_amount"],
                            audit_context=audit_context,
                        )
                    )
                    summary_items.append({"partner_id": partner_id, **structuring, "alert_type": "structuring"})

                round_number = self._detect_round_number(partner_lines)
                if round_number:
                    alerts_to_create.append(
                        self._build_aml_alert_vals(
                            partner_id=partner_id,
                            alert_type="round_number",
                            severity="medium",
                            period_days=period_days,
                            transaction_count=round_number["transaction_count"],
                            total_amount=round_number["total_amount"],
                            audit_context=audit_context,
                        )
                    )
                    summary_items.append({"partner_id": partner_id, **round_number, "alert_type": "round_number"})

                high_frequency = self._detect_high_frequency(partner_lines)
                if high_frequency:
                    alerts_to_create.append(
                        self._build_aml_alert_vals(
                            partner_id=partner_id,
                            alert_type="high_frequency",
                            severity="high",
                            period_days=period_days,
                            transaction_count=high_frequency["transaction_count"],
                            total_amount=high_frequency["total_amount"],
                            audit_context=audit_context,
                        )
                    )
                    summary_items.append(
                        {"partner_id": partner_id, **high_frequency, "alert_type": "high_frequency"}
                    )

            alerts = self.env["ai.aml.alert"].create(alerts_to_create) if alerts_to_create else self.env["ai.aml.alert"]
            if alerts:
                narrative = self._call_narrative(task="aml_narrative", items=summary_items)
                alerts.write({"narrative": narrative})

            high_severity = len(alerts.filtered(lambda rec: rec.severity == "high"))
            partners_flagged = sorted(set(alerts.mapped("partner_id").ids))
            result = {
                "alerts_created": len(alerts),
                "high_severity": high_severity,
                "partners_flagged": partners_flagged,
            }
            self._log_tool_call(
                tool_name="check_aml_patterns",
                args=args,
                result=result,
                success=True,
                latency_ms=self._elapsed_ms(started_at),
                model_used="orchestrator:/tools/narrative",
                audit_context=audit_context,
            )
            return result
        except Exception as exc:
            self._log_tool_call(
                tool_name="check_aml_patterns",
                args=args,
                result={"error": str(exc)},
                success=False,
                latency_ms=self._elapsed_ms(started_at),
                model_used="orchestrator:/tools/narrative",
                audit_context=audit_context,
            )
            raise

    def _get_audit_context(self) -> dict:
        context = self.env.context
        return {
            "conversation_id": context.get("ai_conversation_id")
            or context.get("conversation_id")
            or context.get("x_ai_origin_conversation_id"),
            "message_id": context.get("ai_message_id")
            or context.get("message_id")
            or context.get("x_ai_origin_message_id"),
            "approved_by": context.get("approved_by"),
            "origin_ip": self._get_origin_ip(),
        }

    def _get_origin_ip(self) -> str | None:
        try:
            if http_request and getattr(http_request, "httprequest", None):
                return http_request.httprequest.remote_addr
        except RuntimeError:
            return None
        return None

    def _elapsed_ms(self, started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1000)

    def _get_statement(self, statement_id: int):
        statement = self.env["account.bank.statement"].browse(statement_id)
        if not statement.exists():
            raise ValidationError(_("Bank statement was not found."))
        return statement

    def _load_unreconciled_statement_lines(self, statement) -> list[dict]:
        lines = []
        for line in statement.line_ids.filtered(lambda rec: not getattr(rec, "is_reconciled", False)):
            lines.append(
                {
                    "id": line.id,
                    "amount": getattr(line, "amount", 0.0),
                    "date": str(getattr(line, "date", False) or statement.date or fields.Date.today()),
                    "partner_id": getattr(line.partner_id, "id", False),
                    "ref": getattr(line, "payment_ref", False)
                    or getattr(line, "name", False)
                    or getattr(line, "ref", False)
                    or "",
                    "currency_id": getattr(getattr(line, "currency_id", False), "id", False)
                    or getattr(statement.currency_id, "id", False)
                    or self.env.company.currency_id.id,
                }
            )
        return lines

    def _load_open_move_lines(self, statement) -> list[dict]:
        domain = [
            ("reconciled", "=", False),
            ("parent_state", "=", "posted"),
            ("company_id", "=", statement.company_id.id),
        ]
        move_lines = self.env["account.move.line"].search(domain)
        results = []
        for line in move_lines:
            results.append(
                {
                    "id": line.id,
                    "amount": abs(getattr(line, "amount_residual", 0.0) or getattr(line, "balance", 0.0)),
                    "date": str(line.date),
                    "partner_id": line.partner_id.id,
                    "ref": line.ref or line.name or line.move_name or "",
                    "currency_id": line.currency_id.id or line.company_currency_id.id,
                }
            )
        return results

    def _load_aml_transactions(self, partner_ids: list[int], period_days: int) -> list[dict]:
        start_date = fields.Date.today() - timedelta(days=period_days)
        lines = self.env["account.move.line"].search(
            [
                ("partner_id", "in", partner_ids),
                ("date", ">=", start_date),
                ("parent_state", "=", "posted"),
            ],
            order="date asc, create_date asc, id asc",
        )
        results = []
        for line in lines:
            timestamp = line.create_date or datetime.combine(line.date, dt_time.min)
            results.append(
                {
                    "id": line.id,
                    "partner_id": line.partner_id.id,
                    "amount": abs(getattr(line, "amount_currency", 0.0) or getattr(line, "balance", 0.0)),
                    "date": line.date,
                    "timestamp": timestamp,
                }
            )
        return results

    def _detect_structuring(self, lines: list[dict], threshold: float) -> dict | None:
        matched = [
            line
            for line in lines
            if threshold * 0.85 <= float(line.get("amount", 0.0)) <= threshold * 0.99
        ]
        if len(matched) < 3:
            return None
        return {
            "transaction_count": len(matched),
            "total_amount": sum(float(line.get("amount", 0.0)) for line in matched),
        }

    def _detect_round_number(self, lines: list[dict]) -> dict | None:
        matched = [
            line
            for line in lines
            if float(line.get("amount", 0.0)) > 0 and float(line.get("amount", 0.0)) % 1000 == 0
        ]
        if len(matched) < 3:
            return None
        return {
            "transaction_count": len(matched),
            "total_amount": sum(float(line.get("amount", 0.0)) for line in matched),
        }

    def _detect_high_frequency(self, lines: list[dict]) -> dict | None:
        timestamps = sorted(
            [
                {
                    "timestamp": self._coerce_datetime(line.get("timestamp") or line.get("date")),
                    "amount": float(line.get("amount", 0.0)),
                }
                for line in lines
            ],
            key=lambda item: item["timestamp"],
        )
        timestamps = [item for item in timestamps if item["timestamp"]]
        if len(timestamps) < 11:
            return None

        for start in range(len(timestamps)):
            window = [timestamps[start]]
            for index in range(start + 1, len(timestamps)):
                delta = timestamps[index]["timestamp"] - timestamps[start]["timestamp"]
                if delta <= timedelta(hours=24):
                    window.append(timestamps[index])
                else:
                    break
            if len(window) > 10:
                return {
                    "transaction_count": len(window),
                    "total_amount": sum(item["amount"] for item in window),
                }
        return None

    def _coerce_datetime(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        if value and hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return datetime.combine(value, dt_time.min)
        return None

    def _build_aml_alert_vals(
        self,
        partner_id: int,
        alert_type: str,
        severity: str,
        period_days: int,
        transaction_count: int,
        total_amount: float,
        audit_context: dict,
    ) -> dict:
        period_end = fields.Date.today()
        return {
            "partner_id": partner_id,
            "alert_type": alert_type,
            "severity": severity,
            "period_start": period_end - timedelta(days=period_days),
            "period_end": period_end,
            "transaction_count": transaction_count,
            "total_amount": total_amount,
            "currency_id": self.env.company.currency_id.id,
            "x_ai_origin_conversation_id": audit_context["conversation_id"],
            "x_ai_origin_message_id": audit_context["message_id"],
            "x_ai_created_at": fields.Datetime.now(),
        }

    def _call_narrative(self, task: str, items: list[dict]) -> str:
        token = _mint_orchestrator_jwt(self.env.user.id)
        orch_url = os.environ.get("ORCH_URL", "http://orchestrator:8088").rstrip("/")
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{orch_url}/tools/narrative",
                json={"task": task, "items": items},
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        return response.json().get("narrative", "")

    def _log_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: dict,
        success: bool,
        latency_ms: int,
        model_used: str,
        audit_context: dict,
    ):
        args_json = self._safe_json(args)
        result_json = self._safe_json(result)
        self.env["ai.tool.log"].sudo().create(
            {
                "tool_name": tool_name,
                "model_used": model_used,
                "args_json": args_json,
                "args_sha256": self._sha256(args_json),
                "result_json": result_json,
                "result_sha256": self._sha256(result_json),
                "success": success,
                "latency_ms": latency_ms,
                "tokens_in": 0,
                "tokens_out": 0,
                "est_cost_usd": 0.0,
                "user_id": self.env.user.id,
                "approved_by": audit_context["approved_by"],
                "conversation_id": audit_context["conversation_id"],
                "message_id": audit_context["message_id"],
                "origin_ip": audit_context["origin_ip"],
            }
        )

    def _safe_json(self, payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, default=str)[:20000]

    def _sha256(self, payload: str) -> str:
        return hashlib.sha256(payload.encode()).hexdigest()

    def _render_reconciliation_report_html(self, session) -> str:
        suggestions = session.suggestion_ids.sorted(key=lambda rec: rec.confidence, reverse=True)
        rows = "".join(
            [
                (
                    "<tr>"
                    f"<td>{rec.statement_line_id.display_name or rec.statement_line_id.id}</td>"
                    f"<td>{rec.move_line_id.display_name or rec.move_line_id.id}</td>"
                    f"<td>{rec.confidence}</td>"
                    f"<td>{rec.match_reason or ''}</td>"
                    f"<td>{rec.llm_rationale or ''}</td>"
                    "</tr>"
                )
                for rec in suggestions
            ]
        )
        return f"""
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Reconciliation Report #{session.id}</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
      h1 {{ margin-bottom: 8px; }}
      .summary {{ display: flex; gap: 16px; margin: 16px 0 24px; }}
      .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px 16px; min-width: 160px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
      th {{ background: #f3f4f6; }}
    </style>
  </head>
  <body>
    <h1>AI Reconciliation Report</h1>
    <p>Session #{session.id} · Statement {session.statement_id.display_name or session.statement_id.id}</p>
    <div class=\"summary\">
      <div class=\"card\"><strong>State</strong><br />{session.state}</div>
      <div class=\"card\"><strong>Suggestions</strong><br />{len(suggestions)}</div>
      <div class=\"card\"><strong>Tolerance</strong><br />{session.tolerance_pct}%</div>
      <div class=\"card\"><strong>Date Window</strong><br />{session.date_range_days} days</div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Statement Line</th>
          <th>Move Line</th>
          <th>Confidence</th>
          <th>Reason</th>
          <th>Narrative</th>
        </tr>
      </thead>
      <tbody>{rows or '<tr><td colspan="5">No suggestions generated.</td></tr>'}</tbody>
    </table>
  </body>
</html>
        """.strip()
