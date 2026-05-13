# AI Brain — User Guide

**System:** sgctech.ai (Odoo 19 Community)
**Version:** 19.0.1.0.0
**Last updated:** 2026-05-13

---

## What is AI Brain?

AI Brain is an intelligent assistant embedded directly in your Odoo instance. It connects to Claude (Anthropic) via a secure orchestrator layer and can answer questions, analyse financial data, and help you work faster — all without leaving Odoo.

---

## Getting Started

### How to open a chat session

1. Log in to **sgctech.ai**
2. Navigate to any record (invoice, partner, bank statement, etc.)
3. Open your browser console or use the API endpoint `/ai_brain/chat` (UI panel coming in a future milestone)
4. Send a message — you will receive a reply from Claude in seconds

### First message tips

- Be specific: *"Summarise the outstanding invoices for OSUS Real Estate"* works better than *"show invoices"*
- Mention the record if relevant: *"I'm looking at invoice INV/2026/00016 — why is it unpaid?"*
- Ask follow-up questions in the same conversation thread by reusing the same `conversation_id`

---

## Core Features

### General Q&A

Ask anything business-related. AI Brain answers using its general knowledge and, where tools are wired up, live Odoo data.

**Example prompts:**
- *"What payment terms do we offer?"*
- *"Explain what a reconciliation session is."*
- *"Draft a polite payment reminder email for a 30-day overdue invoice."*

---

### Bank Reconciliation Assistance

AI Brain can suggest matching pairs between bank statement lines and open accounting entries.

**How to trigger:**
- Via the AI Brain Financial Dashboard at `/ai_brain/dashboard`
- Or programmatically through the `suggest_bank_reconciliation` tool

**What it returns:**
- Matched pairs with a confidence score (0–100)
- High-confidence matches (≥ 65) are ready to apply
- Low-confidence matches include an LLM-generated rationale explaining why the match was suggested

**Confidence levels:**

| Score | Meaning | Action |
|---|---|---|
| 90 – 100 | Near-certain match | Apply directly |
| 65 – 89 | Good match | Review and apply |
| < 65 | Uncertain | Manual review required |

---

### AML Pattern Detection

AI Brain screens partners for common Anti-Money Laundering warning signals over a configurable time window.

**Patterns detected:**

| Pattern | Description |
|---|---|
| Structuring | Multiple transactions just below a threshold (85–99% of limit) |
| Round numbers | 3+ transactions with amounts that are exact multiples of 1,000 |
| High frequency | More than 10 transactions within any 24-hour window |

**Output:** Severity-rated alerts (high / medium) stored as `ai.aml.alert` records, visible in the dashboard.

---

### Reconciliation Reports

After running a reconciliation session, generate a printable HTML report:
- Session summary (state, tolerance, date window)
- Full suggestion table with confidence scores and LLM rationales
- Accessible at `/web/content/<attachment_id>`

---

## Financial Dashboard

URL: `https://sgctech.ai/ai_brain/dashboard`

The dashboard shows:
- **Reconciliation sessions** — completed sessions, confidence distribution bar chart, list of sessions with suggestion counts
- **AML alerts** — partner name, alert type, severity badge, date, AI narrative summary
- **Run reconciliation** form — enter a bank statement ID to trigger a new session

The dashboard auto-refreshes every 60 seconds.

---

## Security & Privacy

| Concern | How AI Brain handles it |
|---|---|
| Your data leaving Odoo | Only data you explicitly query is sent to the AI. Sensitive fields are redacted before leaving the server. |
| Who can see conversations | Only the logged-in user and Odoo administrators. |
| AI writing to records | Write actions (reconciliation, alerts) require you to be logged in. All AI-created records are tagged with the conversation ID for full auditability. |
| Audit trail | Every AI call is logged in `ai.tool.log` — tool name, arguments, result, latency, cost, and your user ID. Administrators can review this at any time. |
| Approval for writes | High-impact write actions surface an Approve / Reject confirmation before executing. |

---

## Audit Log (Administrators)

Path: **Settings → Technical → AI Tool Log** (or query `ai.tool.log` via the developer menu)

Each entry records:
- Tool called and arguments
- Result (truncated if large, full SHA-256 hash always stored)
- Success / failure
- Latency in milliseconds
- Estimated cost in USD
- Which user triggered it
- Conversation and message IDs
- Origin IP address

---

## Known Limitations (v19.0.1.0.0)

- The in-app chat **panel** (sidebar in Odoo UI) is planned for a future milestone. Currently the chat is accessible via the JSON-RPC API endpoint `/ai_brain/chat`.
- Reconciliation requires a valid `account.bank.statement` ID. Statements must exist in the database before running.
- AML detection uses simple rule-based patterns only. It is not a substitute for a certified compliance system.
- The AI does not have real-time access to external market data or news.
- Token budget: 50,000 tokens per user per day. If you hit this limit, you will receive a friendly message and can resume the next day.

---

## Troubleshooting

### "Access Denied" on login
Your Odoo session may have expired. Refresh the page and log in again.

### Chat returns an error about the orchestrator
The orchestrator service may be restarting. Wait 30 seconds and try again. If the problem persists, contact your Odoo administrator.

### Reconciliation session shows "error" state
The bank statement ID may be invalid, or the statement may already be fully reconciled. Check the statement in **Accounting → Bank → Statements**.

### AML check returns 0 alerts
This is expected if no partners matched the detection thresholds in the selected time window. Try increasing `period_days` or lowering `threshold_currency`.

---

## Quick Reference

| Task | How |
|---|---|
| Chat with AI | POST `/ai_brain/chat` with `{"prompt": "your question"}` |
| Run reconciliation | Dashboard form or `suggest_bank_reconciliation` tool |
| Generate report | `generate_reconciliation_report` tool with a session ID |
| Check AML | `check_aml_patterns` tool with a list of partner IDs |
| View audit log | `ai.tool.log` model in Odoo |
| View dashboard | `https://sgctech.ai/ai_brain/dashboard` |

---

## Support

For issues or feature requests, contact your system administrator or open a ticket referencing the `ai.tool.log` entry ID for the affected operation.
