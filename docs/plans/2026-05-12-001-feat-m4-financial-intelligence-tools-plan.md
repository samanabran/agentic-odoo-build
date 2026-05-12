---
title: "feat(M4): Financial Intelligence Tools — reconciliation, AML early warning, automated matching"
type: feat
status: active
created: 2026-05-12
milestone: M4
---

# M4 — Financial Intelligence Tools

**Problem:** The Odoo AI Brain chat assistant can answer questions but has no awareness of unreconciled transactions, suspicious financial patterns, or the ability to produce actionable financial reports. Finance teams must manually run reconciliation, check AML exposure, and produce reports outside of Odoo.

**Goal:** Give the AI assistant three active financial capabilities — (1) suggest and score transaction matches, (2) flag AML-pattern risks early, (3) produce an HTML reconciliation + compliance dashboard — all triggerable from the chat panel or on a schedule.

**Scope boundary:** This plan covers Odoo-side tools (models + `@llm_tool` methods), an orchestrator `/tools` router, and a self-contained HTML dashboard controller. CRM auto follow-up is deferred to M5.

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Tool registration | `@llm_tool` decorator on `ai.brain.finance` model | Matches existing vendor pattern; auto-syncs to `llm.tool` table on startup with no extra wiring |
| Matching engine | Deterministic first, LLM fallback for narrative | Pure Python scoring (amount tolerance, date window, partner, ref keywords) is fast, auditable, deterministic; LLM used only for ambiguous pair rationale |
| Report format | HTML via `ir.attachment` | Self-contained, downloadable, renderable in browser; no extra JS framework |
| AML patterns | Heuristic rules + LLM narrative | Structuring, round-number clustering, high-frequency bursts detected heuristically; LLM generates plain-language alert text |
| Orchestrator endpoint | New `app/api/tools.py` router, JWT-authenticated | Same pattern as `app/api/chat.py`; keeps `/tools` concerns separate from conversational `/chat` |
| Dashboard serving | Odoo HTTP controller in `ai_brain` | No extra nginx config; served at `/ai_brain/dashboard` under Odoo session auth |

---

## High-Level Design

*This illustrates the intended approach. It is directional guidance for review, not implementation specification.*

```
Browser / Chat Panel
       │
       ▼
[Odoo ai_brain controller]  ←── GET /ai_brain/dashboard  (HTML view)
       │
       ▼
[ai.brain.finance  @llm_tool methods]
  • suggest_bank_reconciliation(statement_id, tolerance_pct, date_range_days)
  • generate_reconciliation_report(session_id)
  • check_aml_patterns(partner_ids, period_days, threshold_currency)
       │
       ├──► account.bank.statement.line  (unreconciled lines)
       ├──► account.move.line            (open journal items)
       └──► ai.reconciliation.session / suggestion / ai.aml.alert  (results)
       │
       ▼
[Orchestrator  POST /tools/narrative]  ←── JWT auth (same as /chat)
       │
       ▼
[LiteLLM → github-dev / prod-default]
  • Summarise unmatched items in plain language
  • Generate AML alert narrative
  • Suggest reconciliation rationale for low-confidence pairs
```

**Matching confidence scoring (deterministic, additive):**

| Criteria matched | Points |
|---|---|
| Amount exact (0%) + partner + reference keyword overlap | 95 |
| Amount within tolerance_pct + partner | 80 |
| Amount within tolerance_pct + date within date_range_days | 65 |
| Amount within tolerance_pct only | 45 |
| Below 45 or currency mismatch | Manual review required |

---

## Implementation Units

### U1. Odoo data models — reconciliation session, suggestion, AML alert

**Goal:** Persistent storage for AI-generated reconciliation runs and AML alerts.

**Dependencies:** none

**Files:**
- `addons/ai_brain/models/ai_reconciliation.py` (CREATE)
- `addons/ai_brain/models/__init__.py` (MODIFY — add import)
- `addons/ai_brain/security/ir.model.access.csv` (MODIFY — add access rows)
- `addons/ai_brain/tests/test_reconciliation_models.py` (CREATE)

**Approach:**

`ai.reconciliation.session` — one record per run:
- `state`: selection `['draft', 'running', 'done', 'error']`
- `statement_id`: Many2one `account.bank.statement`
- `tolerance_pct`: Float, default 2.0
- `date_range_days`: Integer, default 5
- `suggestion_ids`: One2many to `ai.reconciliation.suggestion`
- `report_attachment_id`: Many2one `ir.attachment`
- `user_id`: Many2one `res.users` — acting user, not superuser
- Inherits `ai.origin.mixin` (CLAUDE.md Section E5)

`ai.reconciliation.suggestion` — one per candidate match pair:
- `session_id`: Many2one `ai.reconciliation.session`
- `statement_line_id`: Many2one `account.bank.statement.line`
- `move_line_id`: Many2one `account.move.line`
- `confidence`: Integer 0–100
- `match_reason`: Char (e.g. `"amount+partner"`)
- `llm_rationale`: Text (LLM explanation, populated for confidence < 65)
- `state`: selection `['suggested', 'accepted', 'rejected']`

`ai.aml.alert` — one per flagged pattern:
- `partner_id`: Many2one `res.partner`
- `alert_type`: selection `['structuring', 'high_frequency', 'round_number', 'velocity']`
- `severity`: selection `['low', 'medium', 'high']`
- `period_start`, `period_end`: Date
- `transaction_count`: Integer
- `total_amount`: Monetary
- `narrative`: Text (LLM-generated)
- `state`: selection `['open', 'reviewed', 'dismissed']`
- Inherits `ai.origin.mixin`

Access rules: `base.group_user` → read-only on suggestions; `account.group_account_user` → full CRUD on all three models.

**Test scenarios:**
- Create `ai.reconciliation.session` → verify `state='draft'`, `user_id` populated
- `confidence` outside 0–100 → `ValidationError` raised
- `ai.aml.alert` with `severity='high'` → `state` defaults to `'open'`
- `ai.origin.mixin` fields present on both session and alert models
- `base.group_user` can read suggestions, cannot write
- `account.group_account_user` can create and update alerts

**Verification:** `make test` passes; psql confirms all three tables exist with correct columns.

---

### U2. Deterministic matching engine

**Goal:** Pure Python scoring of bank statement lines against open journal items, no LLM calls, no ORM dependency.

**Dependencies:** U1

**Files:**
- `addons/ai_brain/services/matching_engine.py` (CREATE)
- `addons/ai_brain/services/__init__.py` (CREATE)
- `addons/ai_brain/tests/test_matching_engine.py` (CREATE)

**Approach:**

`MatchingEngine(tolerance_pct: float, date_range_days: int)` — plain Python class.

`score_pair(stmt_line: dict, move_line: dict) -> tuple[int, str]` — returns `(score, reason_code)`. Pure function; inputs are plain dicts with keys: `amount`, `date`, `partner_id`, `ref`, `currency_id`. Currency mismatch → returns `(0, "currency_mismatch")`. Scoring is additive (see design table above).

`find_candidates(session_vals: dict, stmt_lines: list[dict], move_lines: list[dict]) -> list[dict]` — cartesian score over provided data, returns sorted list of `{stmt_line_id, move_line_id, confidence, match_reason}`. The caller (U3) supplies the data from ORM; this function has no DB access.

Reference keyword overlap uses Jaccard similarity on whitespace-tokenised reference strings; threshold 0.3 for partial credit.

**Test scenarios:**
- Exact amount + same partner + matching reference → score ≥ 90
- Amount within 1.5% + same partner, tolerance_pct=2.0 → score ≥ 70
- Amount within 4%, no partner, date within 2 days → score in [60, 75]
- Amount differs by 10%, tolerance_pct=2.0 → score = 0 (amount breach is disqualifying)
- Currency mismatch → returns `(0, "currency_mismatch")`
- Empty reference on both lines → reference component contributes 0, total unaffected
- `find_candidates` with no move lines → returns empty list, no exception
- 100 statement lines × 200 move lines → completes in < 2 s (performance guard)
- Jaccard overlap of `["INV", "001"]` vs `["INV", "002"]` → 0.33, partial credit awarded

**Verification:** `pytest addons/ai_brain/tests/test_matching_engine.py -v` passes with no live DB.

---

### U3. `@llm_tool` decorated methods — reconciliation and AML

**Goal:** Register three AI-callable tools that orchestrate the matching engine, persist results, and call the orchestrator for LLM narratives.

**Dependencies:** U1, U2

**Files:**
- `addons/ai_brain/models/ai_brain_finance.py` (CREATE)
- `addons/ai_brain/models/__init__.py` (MODIFY — add import)
- `addons/ai_brain/tests/test_finance_tools.py` (CREATE)

**Approach:**

Model `ai.brain.finance` (`_name = 'ai.brain.finance'`, no `_inherit` beyond `mail.thread`). Three methods:

**`suggest_bank_reconciliation(statement_id: int, tolerance_pct: float = 2.0, date_range_days: int = 5) -> dict`**
- Creates session (state='running')
- Loads unreconciled statement lines + open move lines via ORM
- Calls `MatchingEngine.find_candidates(...)`
- Bulk-creates suggestion records
- For confidence < 65: batches those pairs into one `/tools/narrative` call to orchestrator for `llm_rationale`
- Sets state='done'; logs to `ai.tool.log` (CLAUDE.md E4)
- Returns `{"session_id": int, "suggestion_count": int, "high_confidence": int, "manual_review": int}`

**`generate_reconciliation_report(session_id: int) -> dict`**
- Loads session + suggestions via ORM
- Renders self-contained HTML string (inline CSS, no CDN)
- Creates `ir.attachment` with `res_model='ai.reconciliation.session'`, `res_id=session_id`
- Returns `{"url": "/web/content/<attachment_id>", "attachment_id": int}`

**`check_aml_patterns(partner_ids: list[int], period_days: int = 30, threshold_currency: float = 10000.0) -> dict`**
- Queries `account.move.line` for the partners over the period
- Three heuristic checks: structuring (amount 85–99% of threshold), round-number clustering (≥3 moves that are multiples of 1000), high-frequency (>10 transactions in any 24h window)
- Creates `ai.aml.alert` records for each flagged pattern
- Calls orchestrator `/tools/narrative` once for aggregated narrative
- Returns `{"alerts_created": int, "high_severity": int, "partners_flagged": list[int]}`

Decorator annotations (follow vendor `llm_tool` pattern):
- `suggest_bank_reconciliation`: `requires_user_consent=True` (side_effects='write')
- `check_aml_patterns`: `read_only_hint=True`
- `generate_reconciliation_report`: `read_only_hint=False`

**Test scenarios:**
- `suggest_bank_reconciliation` with valid statement_id → session state transitions draft→running→done
- `suggest_bank_reconciliation` with invalid statement_id → `ValidationError`; no orphan session in 'running' state
- `check_aml_patterns([], 30)` → `{"alerts_created": 0, ...}`, no error
- Structuring pattern (5 transactions at 9,800, threshold=10,000) → `ai.aml.alert` created with `alert_type='structuring'`, `severity='high'`
- Round-number pattern (3 transactions of 5,000) → `alert_type='round_number'`
- `generate_reconciliation_report` on non-existent session → `ValueError`
- After `_register_hook`: `env['llm.tool'].search([('decorator_model','=','ai.brain.finance')])` returns 3 records
- Each tool call writes a row to `ai.tool.log`

**Verification:** `make test` passes; Odoo shell confirms 3 tool records in `llm.tool`.

---

### U4. Orchestrator `/tools` router

**Goal:** JWT-authenticated FastAPI endpoint that Odoo tool methods call for LLM narrative generation.

**Dependencies:** none (independent of U1–U3 at code level; Odoo tools call it via HTTP)

**Files:**
- `orchestrator/app/api/tools.py` (CREATE)
- `orchestrator/app/main.py` (MODIFY — include `tools_router`)
- `orchestrator/tests/test_tools_api.py` (CREATE)
- `.env.example` (MODIFY — add `ORCH_URL=http://orchestrator:8088`)

**Approach:**

`POST /tools/narrative` — body: `NarrativeRequest(items: list[dict], task: Literal['reconciliation_rationale', 'aml_narrative'])`. Validates JWT with `decode_access_token`. Builds structured prompt keyed on `task`, calls `_call_litellm` (imported from `app.api.chat`) with `get_active_model()`. Returns `NarrativeResponse(narrative: str)`.

`items` is a list of plain dicts describing the financial data — the orchestrator treats them as untrusted content and wraps them in `<untrusted>...</untrusted>` tags in the prompt (CLAUDE.md E7).

No new LiteLLM routing — uses `get_active_model()` unchanged.

**Test scenarios:**
- Valid JWT + `task='reconciliation_rationale'` + non-empty `items` → 200, `narrative` non-empty
- Valid JWT + `task='aml_narrative'` + `items=[]` → 200, short narrative
- Expired JWT → 401
- Missing Authorization header → 401
- Unknown `task` value → 422
- Endpoint appears in `/openapi.json`

**Verification:** `pytest orchestrator/tests/test_tools_api.py -v` passes; `make test` green.

---

### U5. HTML reconciliation and AML dashboard

**Goal:** Self-contained HTML dashboard served by an Odoo controller; shows live status, auto-refreshes every 60 s.

**Dependencies:** U1, U3

**Files:**
- `addons/ai_brain/controllers/dashboard.py` (CREATE)
- `addons/ai_brain/controllers/__init__.py` (MODIFY — add import)
- `addons/ai_brain/templates/dashboard.xml` (CREATE — QWeb template)
- `addons/ai_brain/__manifest__.py` (MODIFY — add `templates/dashboard.xml` to `data`)

**Approach:**

Controller `AiBrainDashboard` — `GET /ai_brain/dashboard` requires `http.request.session.uid`. Queries:
- Open reconciliation sessions (state='done', suggestion count > 0)
- Last 10 AML alerts (ordered by `create_date desc`)
- Confidence band distribution: count per band 95+, 80–94, 65–79, <65

QWeb template `ai_brain.dashboard` renders self-contained HTML:
- Header: "AI Brain — Financial Intelligence", last-refresh timestamp
- **Reconciliation card**: pending count, CSS confidence bar chart, "Run reconciliation" button
- **AML alerts table**: partner, type, severity badge (colour-coded via inline style), date, narrative excerpt, "Mark reviewed" button
- `<meta http-equiv="refresh" content="60">` auto-refresh
- No `website` module dependency; no external CDN — all CSS inline

`POST /ai_brain/reconcile` — CSRF-protected; calls `env['ai.brain.finance'].suggest_bank_reconciliation(statement_id=...)`, redirects back with flash message.

**Test scenarios:**
- Authenticated GET → 200, `Content-Type: text/html`
- Unauthenticated GET → 302 redirect to `/web/login`
- Zero AML alerts → "No active alerts" message present
- One high-severity alert → severity badge present in response HTML
- CSRF missing on POST → 403
- Valid POST with valid `statement_id` → 302 back to dashboard

**Verification:** `GET http://localhost:8069/ai_brain/dashboard` as admin returns 200 with expected sections; browser renders without external network requests.

---

### U6. Tests and eval harness additions (M4 quota)

**Goal:** Bring eval task count to M4 level (+5 tasks per CLAUDE.md H2).

**Dependencies:** U1–U5

**Files:**
- `orchestrator/eval/tasks/task_reconciliation_suggest.py` (CREATE)
- `orchestrator/eval/tasks/task_aml_check.py` (CREATE)
- `orchestrator/eval/tasks/task_finance_report.py` (CREATE)
- `orchestrator/eval/tasks/task_narrative_quality.py` (CREATE)
- `orchestrator/eval/tasks/task_dashboard_load.py` (CREATE)
- `addons/ai_brain/tests/test_dashboard_controller.py` (CREATE)
- `addons/ai_brain/tests/test_aml_heuristics.py` (CREATE)

**Approach:**

Eval tasks follow existing `task_*.py` pattern (liveness check + assertion):
1. `task_reconciliation_suggest` — chat "reconcile bank statement 1" → verify `ai.reconciliation.session` exists with `state='done'`
2. `task_aml_check` — chat "check AML patterns last 30 days" → response contains partner count or "no alerts found"
3. `task_finance_report` — chat "generate reconciliation report for session 1" → response contains `/web/content/`
4. `task_narrative_quality` — direct POST to `/tools/narrative` with synthetic items → `narrative` key present, length > 50
5. `task_dashboard_load` — GET `/ai_brain/dashboard` as admin session → 200, contains "Financial Intelligence"

**Test scenarios (dashboard controller):**
- Authenticated GET → 200
- Unauthenticated GET → 302
- POST without CSRF → 403
- POST with CSRF + valid `statement_id` → 302 + session created

**Test scenarios (AML heuristics — isolated):**
- Structuring threshold: amounts at 85%, 90%, 99%, 100% of threshold → only first three flagged
- High-frequency: 10 transactions in 23h → not flagged; 11 in 23h → flagged
- Round-number: 2 multiples of 1000 → not flagged; 3 → flagged

**Verification:** `make eval` shows 5 new tasks passing or skip-annotated; `make test` green.

---

## Scope Boundaries

### In Scope (M4)
- `ai.reconciliation.session`, `ai.reconciliation.suggestion`, `ai.aml.alert` Odoo models
- Deterministic matching engine (pure Python, no LLM)
- Three `@llm_tool` decorated methods auto-registered at startup
- Orchestrator `/tools/narrative` endpoint
- HTML dashboard at `/ai_brain/dashboard`
- 5 new eval tasks, new unit tests

### Deferred to M5
- CRM auto follow-up and sequence-triggered reminders
- Scheduled/cron reconciliation runs (requires job queue)
- Reconciliation auto-apply without human approval (blocked by E3 approval-flow requirement)
- Grafana panel for reconciliation metrics (M8)

### Outside This Plan
- Direct bank feed import (requires OFX/CSV parser — separate scope)
- Regulatory AML reporting (SARs, CTRs) — separate compliance module

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `account.bank.statement` API differs in Odoo 18 vs 16 | Medium | High | Read model definition from running container before U2 implementation; adjust field names accordingly |
| LLM narrative calls add latency to `suggest_bank_reconciliation` | High | Medium | Batch all low-confidence pairs into one `/tools/narrative` call per session |
| AML false-positive rate too high in demo data | Medium | Medium | Heuristic thresholds configurable via `ir.config_parameter`; alerts default to `state='open'` for human review |
| Vendor diff violation | Low | Critical | All code in `addons/ai_brain/`; verify with `git -C addons/vendor/odoo-llm diff --quiet HEAD` before merge |

---

## Prerequisites

- M3 PR #13 merged to `main` before this branch is created
- `account` Odoo module installed in `ai_brain_dev` DB
- `ORCH_URL` env var added to `.env` and `.env.example`
- At least one working LLM provider key in `.env` (for narrative calls)

---

## ADR Required

**ADR 0014** — Matching engine approach: deterministic-first vs full LLM classification.
Decision: deterministic Python scoring; LLM used only for plain-language rationale on low-confidence pairs.
Rationale: auditability of match decisions, cost control, deterministic test coverage.
