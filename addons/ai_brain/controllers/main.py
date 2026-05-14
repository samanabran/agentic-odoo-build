# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict
from datetime import timedelta

import requests

from odoo import fields, http
from odoo.http import request


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _mint_jwt(user_id: int, ttl: int = 300) -> str:
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


_HTML_SYSTEM = (
    "CRITICAL RULE: Output ONLY an HTML fragment — NO <!DOCTYPE>, NO <html>, NO <head>, "
    "NO <body>, NO <style>, NO <script> tags. Do NOT use inline styles except for "
    "ai-progress-fill width (e.g. style=\"width:65%\"). Use ONLY these pre-styled classes:\n\n"
    "KPI METRIC CARDS:\n"
    "<div class=\"ai-metric-grid\">"
    "<div class=\"ai-metric-card [danger|warning|success]\">"
    "<div class=\"ai-metric-label\">LABEL</div>"
    "<div class=\"ai-metric-value\">Value</div>"
    "<div class=\"ai-metric-sub\">Subtitle</div>"
    "</div></div>\n\n"
    "PROGRESS BARS (for budget/usage %):\n"
    "<div class=\"ai-progress-grid\">"
    "<div class=\"ai-progress-item [danger|warning|success|info]\">"
    "<div class=\"ai-progress-label\">Label</div>"
    "<div class=\"ai-progress-track\"><div class=\"ai-progress-fill\" style=\"width:65%\"></div></div>"
    "<div class=\"ai-progress-pct\">65% Used</div>"
    "<div class=\"ai-progress-sub\">$35,000 Remaining</div>"
    "</div></div>\n\n"
    "DATA TABLES:\n"
    "<table><thead><tr><th>Col</th></tr></thead><tbody><tr><td>Val</td></tr></tbody></table>\n\n"
    "ALERTS: <div class=\"ai-alert [critical|warning|info|success]\">Message</div>\n"
    "BADGES: <span class=\"badge-[ok|warn|danger|info]\">Text</span>\n"
    "HEADINGS: <h1>Dashboard Title</h1> <h2>Section</h2> <h3>Subsection</h3>\n\n"
    "Start directly with an HTML element. No preamble, no markdown, no ``` fences."
)


def _call_orchestrator(prompt: str, thread_id: int = 0) -> dict:
    user_id = request.env.user.id
    token = _mint_jwt(user_id)
    orch_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000").rstrip("/")
    full_prompt = f"{_HTML_SYSTEM}\n\n{prompt}"
    resp = requests.post(
        f"{orch_url}/chat",
        json={"prompt": full_prompt, "thread_id": thread_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


def _model_exists(env, model_name: str) -> bool:
    return model_name in env.registry


def _fmt(amount, currency=None) -> str:
    sym = currency.symbol if currency else ""
    return f"{sym}{float(amount):,.2f}"


def _aging_buckets(moves, today) -> dict:
    b = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
    for m in moves:
        due = m.invoice_date_due
        residual = float(m.amount_residual)
        if not due or due >= today:
            b["current"] += residual
        else:
            days = (today - due).days
            if days <= 30:
                b["1_30"] += residual
            elif days <= 60:
                b["31_60"] += residual
            elif days <= 90:
                b["61_90"] += residual
            else:
                b["over_90"] += residual
    return b


# ── Finance fetchers ─────────────────────────────────────────────────────────

def _fetch_summary(env, today, currency):
    recv = env["account.move"].search([
        ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
        ("payment_state", "not in", ["paid", "reversed"]),
    ])
    pay = env["account.move"].search([
        ("move_type", "=", "in_invoice"), ("state", "=", "posted"),
        ("payment_state", "not in", ["paid", "reversed"]),
    ])
    od_recv = sum(m.amount_residual for m in recv if m.invoice_date_due and m.invoice_date_due < today)
    od_pay = sum(m.amount_residual for m in pay if m.invoice_date_due and m.invoice_date_due < today)
    c = currency
    return (
        f"LIVE ODOO DATA — Financial Summary as of {today}\n"
        f"Outstanding receivables: {_fmt(sum(recv.mapped('amount_residual')), c)} ({len(recv)} invoices)\n"
        f"  Overdue: {_fmt(od_recv, c)}\n"
        f"Outstanding payables: {_fmt(sum(pay.mapped('amount_residual')), c)} ({len(pay)} bills)\n"
        f"  Overdue: {_fmt(od_pay, c)}\n"
    )


def _fetch_invoices(env, today, currency):
    moves = env["account.move"].search([
        ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
        ("payment_state", "not in", ["paid", "reversed"]),
    ])
    b = _aging_buckets(moves, today)
    top5 = sorted(moves, key=lambda m: m.amount_residual, reverse=True)[:5]
    top5_lines = "\n".join(
        f"  {m.name} | {m.partner_id.name} | due {m.invoice_date_due} | {_fmt(m.amount_residual, currency)}"
        for m in top5
    )
    return (
        f"LIVE ODOO DATA — Outstanding Customer Invoices as of {today}\n"
        f"Current: {_fmt(b['current'], currency)}\n"
        f"1-30 days overdue: {_fmt(b['1_30'], currency)}\n"
        f"31-60 days overdue: {_fmt(b['31_60'], currency)}\n"
        f"61-90 days overdue: {_fmt(b['61_90'], currency)}\n"
        f"Over 90 days overdue: {_fmt(b['over_90'], currency)}\n"
        f"Total: {_fmt(sum(b.values()), currency)} across {len(moves)} invoices\n"
        f"Top 5 open invoices:\n{top5_lines}\n"
    )


def _fetch_cash(env, today, currency):
    journals = env["account.journal"].search([("type", "in", ["bank", "cash"])])
    lines = []
    total = 0.0
    for j in journals:
        bal = float(getattr(j, "current_statement_balance", 0.0) or 0.0)
        lines.append(f"  {j.name}: {_fmt(bal, currency)}")
        total += bal
    return (
        f"LIVE ODOO DATA — Cash Position as of {today}\n"
        + ("\n".join(lines) if lines else "  No bank/cash journals found.")
        + f"\nTotal liquid: {_fmt(total, currency)}\n"
    )


def _fetch_reconcile(env, today):
    try:
        lines = env["account.bank.statement.line"].search([("is_reconciled", "=", False)], limit=500)
    except Exception:
        lines = env["account.bank.statement.line"].search([], limit=500)
        lines = lines.filtered(lambda l: not getattr(l, "is_reconciled", True))
    if not lines:
        return f"LIVE ODOO DATA — Reconciliation Status as of {today}\nAll statement lines reconciled.\n"
    total = sum(abs(float(getattr(l, "amount", 0.0))) for l in lines)
    oldest = min((l.date for l in lines if l.date), default=None)
    return (
        f"LIVE ODOO DATA — Reconciliation Status as of {today}\n"
        f"Unreconciled lines: {len(lines)}, combined value: {_fmt(total)}, oldest: {oldest}\n"
    )


def _fetch_aml(env, today):
    start = today - timedelta(days=30)
    lines = env["account.move.line"].search([
        ("date", ">=", start), ("parent_state", "=", "posted"), ("partner_id", "!=", False),
    ], limit=1000, order="date asc")
    by_partner = defaultdict(list)
    for l in lines:
        by_partner[l.partner_id.id].append(
            abs(float(getattr(l, "amount_currency", 0.0) or getattr(l, "balance", 0.0)))
        )
    alerts = []
    for pid, amounts in by_partner.items():
        partner = env["res.partner"].browse(pid)
        if len(amounts) > 10:
            alerts.append(f"  HIGH-FREQ: {partner.name} — {len(amounts)} txn, total {_fmt(sum(amounts))}")
        if len([a for a in amounts if a > 0 and a % 1000 == 0]) >= 3:
            alerts.append(f"  ROUND-NUMBER: {partner.name} — {len([a for a in amounts if a % 1000 == 0])} round txn")
        if len([a for a in amounts if 8500 <= a <= 9900]) >= 3:
            alerts.append(f"  STRUCTURING: {partner.name} — {len([a for a in amounts if 8500 <= a <= 9900])} near-threshold txn")
    return (
        f"LIVE ODOO DATA — AML Scan (30 days, {len(lines)} transactions)\n"
        + (("\n".join(alerts) + "\n") if alerts else "No high-severity patterns detected.\n")
    )


def _fetch_receivables(env, today, currency):
    moves = env["account.move"].search([
        ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
        ("payment_state", "not in", ["paid", "reversed"]),
    ])
    b = _aging_buckets(moves, today)
    by_partner = defaultdict(float)
    for m in moves:
        if m.invoice_date_due and m.invoice_date_due < today:
            by_partner[m.partner_id.name] += float(m.amount_residual)
    top5 = sorted(by_partner.items(), key=lambda x: x[1], reverse=True)[:5]
    return (
        f"LIVE ODOO DATA — Aged Receivables as of {today}\n"
        f"Current: {_fmt(b['current'], currency)} | 1-30d: {_fmt(b['1_30'], currency)} | "
        f"31-60d: {_fmt(b['31_60'], currency)} | 61-90d: {_fmt(b['61_90'], currency)} | "
        f"90+d: {_fmt(b['over_90'], currency)}\n"
        f"Total: {_fmt(sum(b.values()), currency)}\n"
        + ("Top overdue customers:\n" + "\n".join(f"  {n}: {_fmt(a, currency)}" for n, a in top5) + "\n" if top5 else "")
    )


def _fetch_payables(env, today, currency):
    moves = env["account.move"].search([
        ("move_type", "=", "in_invoice"), ("state", "=", "posted"),
        ("payment_state", "not in", ["paid", "reversed"]),
    ])
    b = _aging_buckets(moves, today)
    overdue = sorted(
        [(m.partner_id.name, float(m.amount_residual), m.invoice_date_due)
         for m in moves if m.invoice_date_due and m.invoice_date_due < today],
        key=lambda x: x[1], reverse=True
    )
    return (
        f"LIVE ODOO DATA — Aged Payables as of {today}\n"
        f"Current: {_fmt(b['current'], currency)} | 1-30d: {_fmt(b['1_30'], currency)} | "
        f"31-60d: {_fmt(b['31_60'], currency)} | 61-90d: {_fmt(b['61_90'], currency)} | "
        f"90+d: {_fmt(b['over_90'], currency)}\n"
        f"Total: {_fmt(sum(b.values()), currency)}\n"
        + ("Top overdue vendors:\n" + "\n".join(f"  {n}: {_fmt(a, currency)} (due {d})" for n, a, d in overdue[:5]) + "\n" if overdue else "")
    )


def _fetch_tax(env, today, currency):
    month_start = today.replace(day=1)
    tax_lines = env["account.move.line"].search([
        ("tax_line_id", "!=", False), ("date", ">=", month_start), ("parent_state", "=", "posted"),
    ])
    sales_tax = sum(abs(float(l.balance)) for l in tax_lines if l.move_id.move_type in ("out_invoice", "out_refund"))
    purchase_tax = sum(abs(float(l.balance)) for l in tax_lines if l.move_id.move_type in ("in_invoice", "in_refund"))
    net = sales_tax - purchase_tax
    return (
        f"LIVE ODOO DATA — VAT/Tax ({month_start} to {today})\n"
        f"VAT collected: {_fmt(sales_tax, currency)} | VAT paid: {_fmt(purchase_tax, currency)}\n"
        f"Net {'payable' if net >= 0 else 'refundable'}: {_fmt(abs(net), currency)}\n"
    )


def _fetch_pnl(env, today, currency):
    month_start = today.replace(day=1)
    lines = env["account.move.line"].search([
        ("date", ">=", month_start), ("date", "<=", today), ("parent_state", "=", "posted"),
        ("account_id.account_type", "in", ["income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"]),
    ])
    revenue = sum(-float(l.balance) for l in lines if l.account_id.account_type in ("income", "income_other"))
    expenses = sum(float(l.balance) for l in lines if l.account_id.account_type in ("expense", "expense_depreciation", "expense_direct_cost"))
    net = revenue - expenses
    return (
        f"LIVE ODOO DATA — P&L Snapshot ({month_start} to {today})\n"
        f"Revenue: {_fmt(revenue, currency)} | Expenses: {_fmt(expenses, currency)}\n"
        f"Net {'profit' if net >= 0 else 'loss'}: {_fmt(abs(net), currency)}\n"
    )


# ── HR / Payroll fetchers ────────────────────────────────────────────────────

def _fetch_hr_summary(env, today):
    if not _model_exists(env, "hr.employee"):
        return "LIVE ODOO DATA — HR: module not installed.\n"
    employees = env["hr.employee"].search([("active", "=", True)])
    by_dept = defaultdict(int)
    for e in employees:
        by_dept[e.department_id.name or "Unassigned"] += 1
    dept_lines = "\n".join(f"  {dept}: {cnt}" for dept, cnt in sorted(by_dept.items()))
    return (
        f"LIVE ODOO DATA — HR Summary as of {today}\n"
        f"Total active employees: {len(employees)}\n"
        f"By department:\n{dept_lines}\n"
    )


def _fetch_payroll(env, today, currency):
    if not _model_exists(env, "hr.payslip"):
        return "LIVE ODOO DATA — Payroll: module not installed.\n"
    month_start = today.replace(day=1)
    slips = env["hr.payslip"].search([
        ("date_from", ">=", month_start), ("state", "in", ["done", "paid"]),
    ])
    total_net = 0.0
    total_gross = 0.0
    for slip in slips:
        for line in slip.line_ids:
            if line.code == "NET":
                total_net += float(line.total)
            if line.code == "GROSS":
                total_gross += float(line.total)
    return (
        f"LIVE ODOO DATA — Payroll ({month_start} to {today})\n"
        f"Payslips processed: {len(slips)}\n"
        f"Total gross: {_fmt(total_gross, currency)}\n"
        f"Total net: {_fmt(total_net, currency)}\n"
    )


def _fetch_leaves(env, today):
    if not _model_exists(env, "hr.leave"):
        return "LIVE ODOO DATA — Leaves: module not installed.\n"
    pending = env["hr.leave"].search([("state", "in", ["confirm", "validate1"])])
    return (
        f"LIVE ODOO DATA — Leave Requests as of {today}\n"
        f"Pending approval: {len(pending)} requests\n"
        + ("\n".join(f"  {l.employee_id.name}: {l.holiday_status_id.name} ({l.date_from} – {l.date_to})" for l in pending[:10]) + "\n" if pending else "")
    )


# ── Sales / CRM fetchers ─────────────────────────────────────────────────────

def _fetch_sales_pipeline(env, today, currency):
    if not _model_exists(env, "crm.lead"):
        return "LIVE ODOO DATA — CRM: module not installed.\n"
    leads = env["crm.lead"].search([("active", "=", True), ("type", "=", "opportunity")])
    by_stage = defaultdict(lambda: {"count": 0, "value": 0.0})
    for l in leads:
        stage = l.stage_id.name or "Unknown"
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += float(getattr(l, "expected_revenue", 0.0) or 0.0)
    stage_lines = "\n".join(
        f"  {s}: {d['count']} leads, {_fmt(d['value'], currency)}"
        for s, d in sorted(by_stage.items())
    )
    total_pipeline = sum(d["value"] for d in by_stage.values())
    return (
        f"LIVE ODOO DATA — CRM Pipeline as of {today}\n"
        f"Total pipeline value: {_fmt(total_pipeline, currency)} across {len(leads)} leads\n"
        f"By stage:\n{stage_lines}\n"
    )


def _fetch_sales_performance(env, today, currency):
    month_start = today.replace(day=1)
    invoices = env["account.move"].search([
        ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
        ("invoice_date", ">=", month_start), ("invoice_date", "<=", today),
    ])
    by_salesperson = defaultdict(float)
    for inv in invoices:
        rep = getattr(inv, "invoice_user_id", None) or getattr(inv, "user_id", None)
        name = rep.name if rep else "Unassigned"
        by_salesperson[name] += float(inv.amount_untaxed)
    top = sorted(by_salesperson.items(), key=lambda x: x[1], reverse=True)[:10]
    total = sum(v for _, v in top)
    return (
        f"LIVE ODOO DATA — Sales Performance ({month_start} to {today})\n"
        f"Total invoiced: {_fmt(total, currency)}\n"
        f"By salesperson:\n"
        + "\n".join(f"  {n}: {_fmt(a, currency)}" for n, a in top) + "\n"
    )


def _fetch_payroll_vs_revenue(env, today, currency):
    pnl = _fetch_pnl(env, today, currency)
    payroll = _fetch_payroll(env, today, currency)
    return pnl + "\n" + payroll


# ── Universal context snapshot (for custom questions) ───────────────────────

def _build_universal_snapshot(env, today, currency) -> str:
    sections = []

    # Finance
    try:
        sections.append(_fetch_summary(env, today, currency))
    except Exception as e:
        sections.append(f"[Finance summary unavailable: {e}]\n")

    try:
        sections.append(_fetch_cash(env, today, currency))
    except Exception as e:
        sections.append(f"[Cash data unavailable: {e}]\n")

    try:
        sections.append(_fetch_pnl(env, today, currency))
    except Exception as e:
        sections.append(f"[P&L unavailable: {e}]\n")

    # HR
    try:
        sections.append(_fetch_hr_summary(env, today))
    except Exception as e:
        sections.append(f"[HR summary unavailable: {e}]\n")

    # Payroll
    try:
        sections.append(_fetch_payroll(env, today, currency))
    except Exception as e:
        sections.append(f"[Payroll unavailable: {e}]\n")

    # Sales/CRM
    try:
        sections.append(_fetch_sales_performance(env, today, currency))
    except Exception as e:
        sections.append(f"[Sales performance unavailable: {e}]\n")

    try:
        sections.append(_fetch_sales_pipeline(env, today, currency))
    except Exception as e:
        sections.append(f"[CRM pipeline unavailable: {e}]\n")

    return "\n".join(s for s in sections if s)


# ── Action registry ──────────────────────────────────────────────────────────

_FETCHERS = {
    "summary":          lambda env, t, c: _fetch_summary(env, t, c),
    "invoices":         lambda env, t, c: _fetch_invoices(env, t, c),
    "cash":             lambda env, t, c: _fetch_cash(env, t, c),
    "reconcile":        lambda env, t, c: _fetch_reconcile(env, t),
    "aml":              lambda env, t, c: _fetch_aml(env, t),
    "receivables":      lambda env, t, c: _fetch_receivables(env, t, c),
    "payables":         lambda env, t, c: _fetch_payables(env, t, c),
    "tax":              lambda env, t, c: _fetch_tax(env, t, c),
    "pnl":              lambda env, t, c: _fetch_pnl(env, t, c),
    "hr":               lambda env, t, c: _fetch_hr_summary(env, t),
    "payroll":          lambda env, t, c: _fetch_payroll(env, t, c),
    "leaves":           lambda env, t, c: _fetch_leaves(env, t),
    "sales":            lambda env, t, c: _fetch_sales_performance(env, t, c),
    "pipeline":         lambda env, t, c: _fetch_sales_pipeline(env, t, c),
    "payroll_revenue":  lambda env, t, c: _fetch_payroll_vs_revenue(env, t, c),
}

_INSTRUCTIONS = {
    "summary": (
        "Produce an executive financial dashboard. "
        "Show key metrics (receivables, payables, overdue amounts) as ai-metric-card elements with danger/warning/success colouring. "
        "Add an ai-alert for any urgent items requiring immediate action."
    ),
    "invoices": (
        "Produce an invoice aging report. "
        "Show the four aging buckets and totals in an ai-metric-grid. "
        "List top outstanding invoices in a table with columns: Invoice, Customer, Due Date, Amount, Status badge. "
        "Add a warning or critical ai-alert if any bucket exceeds normal thresholds."
    ),
    "cash": (
        "Produce a cash position report. "
        "Show each bank/cash account as an ai-metric-card. "
        "Show total liquid cash as a prominent metric. "
        "Add an info or warning ai-alert commenting on liquidity adequacy."
    ),
    "reconcile": (
        "Produce a reconciliation status report. "
        "Show unreconciled count and combined value as metric cards with appropriate danger/warning/success colouring. "
        "Explain the risk of leaving items open in an ai-alert. "
        "If all reconciled, show a success ai-alert."
    ),
    "aml": (
        "Produce an AML scan report. "
        "List each alert in a table with columns: Pattern, Partner, Count, Severity badge (badge-danger/badge-warn/badge-info). "
        "Add a critical ai-alert if any high-severity items exist, or a success alert if no patterns detected."
    ),
    "receivables": (
        "Produce an aged receivables report. "
        "Show aging buckets (Current, 1-30d, 31-60d, 61-90d, 90+d) as ai-metric-cards with danger colouring on overdue buckets. "
        "List top overdue customers in a table with columns: Customer, Amount, Days Overdue, Priority badge."
    ),
    "payables": (
        "Produce an aged payables report. "
        "Show aging buckets as ai-metric-cards with danger colouring on overdue buckets. "
        "List top overdue vendors in a table with columns: Vendor, Amount, Due Date, Status badge. "
        "Add a critical ai-alert for any items at risk of late-payment penalties."
    ),
    "tax": (
        "Produce a VAT/tax summary. "
        "Show VAT collected, VAT paid, and net payable/refundable as ai-metric-cards. "
        "Add an info ai-alert confirming the net position and flagging any filing deadline risk."
    ),
    "pnl": (
        "Produce a P&L snapshot. "
        "Show Revenue, Expenses, and Net Profit/Loss as ai-metric-cards with success/danger colouring based on sign. "
        "Add an ai-alert commenting on margin health and any trend concerns."
    ),
    "hr": (
        "Produce an HR headcount report. "
        "Show total headcount as a prominent metric card. "
        "List departments and employee counts in a table with columns: Department, Headcount. "
        "Add an info ai-alert flagging any department imbalances or staffing concerns."
    ),
    "payroll": (
        "Produce a payroll cost report. "
        "Show gross pay, net pay, and payslip count as ai-metric-cards. "
        "Add an info or warning ai-alert commenting on payroll trends or anomalies."
    ),
    "leaves": (
        "Produce a leave requests report. "
        "Show pending approval count as a metric card. "
        "List pending requests in a table with columns: Employee, Leave Type, From, To. "
        "Add a warning ai-alert if any leave creates coverage risk."
    ),
    "sales": (
        "Produce a sales performance report. "
        "Show total invoiced as a prominent metric card. "
        "List top performers in a table with columns: Salesperson, Amount, Share badge. "
        "Add an info ai-alert identifying top performer and any underperforming areas."
    ),
    "pipeline": (
        "Produce a CRM pipeline report. "
        "Show total pipeline value and lead count as metric cards. "
        "List pipeline by stage in a table with columns: Stage, Leads, Value. "
        "Add an ai-alert assessing pipeline health and forecast risk."
    ),
    "payroll_revenue": (
        "Produce a payroll-vs-revenue analysis. "
        "Show revenue, payroll cost, and labour cost ratio as ai-metric-cards with danger colouring if ratio exceeds 50%. "
        "Add a critical or success ai-alert commenting on sustainability."
    ),
}


class AiBrainController(http.Controller):

    @http.route("/ai_brain/chat", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def chat(self, prompt: str, thread_id: int = 0, res_model: str = None, res_id: int = None):
        return _call_orchestrator(prompt, thread_id)

    @http.route("/ai_brain/finance", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def finance(self, action: str = "custom", prompt: str = ""):
        env = request.env
        today = fields.Date.today()
        currency = env.company.currency_id

        if action == "custom":
            # Pull a full cross-app snapshot so the LLM can answer any question
            context = _build_universal_snapshot(env, today, currency)
            instruction = prompt or "Give a comprehensive overview of the business based on the data above."
        elif action in _FETCHERS:
            try:
                context = _FETCHERS[action](env, today, currency)
            except Exception as exc:
                context = f"[Data fetch error: {exc}]\n"
            instruction = _INSTRUCTIONS.get(action, prompt or "Summarise the data above.")
        else:
            context = ""
            instruction = prompt or "No data available."

        extra = f"\n\nAdditional question from user: {prompt}" if prompt and action not in ("custom", "") else ""
        full_prompt = (
            f"REPORT TYPE: {instruction}\n\nLIVE DATA:\n{context}{extra}"
            if context
            else instruction
        )

        return _call_orchestrator(full_prompt)
