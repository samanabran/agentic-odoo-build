# ADR 0013 — M3 conversation model architecture

**Date:** 2026-05-07
**Status:** Accepted (PR #10)
**Branch:** docs/adr-0013-m3-architecture

---

## Context

M3 introduces the conversation layer (`ai.conversation`, `ai.message` per
CLAUDE.md milestone table). A pre-planning diagnostic (PR #10 prep) revealed:

- `llm.thread` (vendor module `llm_thread`) is the live conversation table,
  installed with 37 vendor modules in M2. The full OWL chat UI (container,
  thread header, chatter patches, client action) already exists in
  `llm_thread/static/src/`.
- `mail.message` is the live message table. `llm_thread` does not define a
  separate message table — chat messages are persisted as `mail.message` rows
  linked to `llm_thread` records (confirmed by `llm_thread/models/mail_message.py`
  and absence of `llm_message` table in live DB).
- The orchestrator currently has only `/health` and `/admin` routes (at
  `/orchestrator/app/api/health.py` and `admin.py`). It is not in the chat path today.
- The vendor JS streaming call is a single URL in
  `llm_thread/static/src/services/llm_store_service.js`:
  `let url = \`/llm/thread/generate?thread_id=${threadId}\`;`
  All other OWL components route through this service.
- The kickoff doc (`kickoff-odoo-ai-brain.html` §4.4, lines 557–563) mandates
  orchestrator participation in chat (verbatim):
  > "User types in the chat panel; Odoo controller `/ai_brain/chat` persists
  > an `ai.message` and issues a JWT. Orchestrator receives prompt + JWT +
  > context (res_model, res_id). Orchestrator loads conversation history and
  > runs RAG to fetch relevant chunks. LLM is called in a planning loop
  > (ReAct): Thought → Action (tool call) → Observation → repeat, capped at
  > 8 steps."
- ADR 0001 line 33: "orchestrator never calls providers directly." ADR 0001
  line 41: "`PRIVATE_MODE=true` routing to Ollama requires no orchestrator
  code path changes." These imply the orchestrator was always intended to be
  in the chat path; current state drifts from this.
- M3 kickoff acceptance criteria (`kickoff-odoo-ai-brain.html` lines 367–375,
  verbatim): "Replace the placeholder systray with a real OWL side panel:
  conversation list, current thread, input box, context chip showing the
  active record (res_model, res_id) when on a form view. Wire it to call
  llm_assistant under the hood (do not duplicate logic). Preserve conversation
  history per user across sessions."
- No M3 risk register existed prior to this ADR.

---

## Decisions

### Decision 1 — Classical inheritance for ai.conversation and ai.message

`ai.conversation` and `ai.message` are **not** new Odoo `_name` values with
their own tables. They are conceptual labels for AI-domain fields added to
`llm.thread` and `mail.message` via classical `_inherit`:

```python
# ai_brain/models/ai_conversation.py
class AIConversation(models.Model):
    _inherit = "llm.thread"
    # adds AI-domain fields (res_model, res_id, ai_user_id, etc.)
    # to the existing llm_thread table

# ai_brain/models/ai_message.py
class AIMessage(models.Model):
    _inherit = "mail.message"
    # adds token_count_input, token_count_output, total_cost_usd, etc.
    # to the existing mail_message table
```

**Rationale:**

- **M2 precedent:** `llm_provider_override.py` and `llm_provider_usage.py`
  both used `_inherit = "llm.provider"` without `_name` — same pattern,
  same table, no new schema.
- **Prototype inheritance rejected:** Setting `_name = "ai.conversation"` +
  `_inherit = "llm.thread"` creates a NEW table `ai_conversation`. Vendor
  controller calls `env["llm.thread"].browse(id)` — records created via
  `env["ai.conversation"]` would NOT be visible there. Breaks backward
  compatibility with all installed vendor modules.
- **Delegation (`_inherits`) rejected:** Joins on every ORM call; reserved
  for genuinely separate entities. Not applicable here.

**CLAUDE.md naming reconciliation:**

The CLAUDE.md key-models table lists `ai.conversation` and `ai.message` as
model names. This ADR clarifies they are conceptual labels, not Odoo `_name`
values. A follow-up erratum to CLAUDE.md updating the table to read
`llm.thread (extended)` and `mail.message (extended)` is recommended but is
NOT part of this PR.

**ai.origin.mixin clarification:**

The existing `ai.origin.mixin` (fields `x_ai_origin_conversation_id`,
`x_ai_origin_message_id`, `x_ai_created_at`) tags **downstream business
records** (e.g. `sale.order`) with the conversation that produced an
AI-initiated write. It is NOT applied to `ai.conversation` or `ai.message`
themselves — that would create a circular self-reference with no semantic
value. The mixin fields are Char (storing IDs as strings), so no Many2one
dependency on `ai.conversation` existing as a real model name.

---

### Decision 2 — Orchestrator participates in chat path; M3 implements γ-thin

The chat path goes through the orchestrator per the kickoff canonical flow.
Three γ sub-options were evaluated for M3 scope:

| Option | Scope | Decision |
|--------|-------|----------|
| γ-thin | JWT plumbing + single LiteLLM streaming call. No RAG, no ReAct, no tools. | **CHOSEN for M3** |
| γ-mid | γ-thin + history loading from prior `ai.message` rows | Deferred to M3 integration or M4 entry |
| γ-thick | Full kickoff flow: RAG + ReAct + tool execution + approval cards | Deferred to M4+ explicitly |

**Rationale for γ-thin:**

- The full kickoff flow (RAG, ReAct, tool execution) is 2–3 PRs minimum with
  their own risk registers. Conflating all of that with the model layer makes
  M3 unreviewable and reverts to M2's pre-ADR-0006 problem of unbounded scope.
- γ-thin produces an honest end-to-end demo: user types → `/ai_brain/chat`
  mints JWT → orchestrator validates → LiteLLM streams response back. Every
  integration boundary is exercised; nothing is faked.
- M4 entry criteria gain a deliberate item: implement γ-mid (history loading)
  then γ-thick (RAG + ReAct + tools), each with its own risk-registered milestone.

**Out of scope for M3 (explicitly deferred to M4+):**

- RAG over knowledge base (`llm_knowledge` / `llm_pgvector` integration)
- ReAct planning loop (LangGraph or equivalent)
- Tool execution coordination via Odoo JSON-RPC
- Streaming approval cards for write tools
- Per-user daily and per-tenant monthly budget enforcement (token fields land
  in M3 as R5; enforcement is M4)

---

### Decision 3 — JS route intercept is single-point in llm_store_service.js

The diagnostic confirmed exactly **one** direct `/llm/thread/...` route call
in all of `llm_thread/static/src/`:

```
llm_store_service.js:  let url = `/llm/thread/generate?thread_id=${threadId}`;
```

All other OWL components (`llm_chat_container`, `llm_thread_header`,
`composer_patch`, `chatter_patch`, `llm_assistant` patches) route through
`llm_store_service`. Therefore M3's JS change is a single OWL service patch
in `ai_brain` that overrides the URL to call `/ai_brain/chat` instead.

The vendor `/llm/thread/generate` route is preserved for non-ai_brain
consumers (other vendor modules or downstream integrators that call it
directly). R2 verifies this.

---

### Decision 4 — ADR 0001 is amended, not superseded

ADR 0001 line 33 ("orchestrator never calls providers directly") is a
constraint on the **orchestrator-to-LLM leg**: when the orchestrator talks to
LLMs, it goes through LiteLLM, not raw SDK calls. M3 honors this — the new
`/chat` orchestrator endpoint calls LiteLLM exactly as the eval harness does.

ADR 0001 line 41 ("`PRIVATE_MODE=true` routing to Ollama requires no
orchestrator code path changes") implies the orchestrator was always intended
to be in the chat path. The current state (orchestrator absent from
interactive chat) drifted from this intent. M3 corrects the drift.

ADR 0001 is appended (not superseded) with a "M3 reconciliation" note in this
same PR.

---

## Risk register

### R1 — Vendor route intercept (single-point)

**Constraint:** AI-aware chat traffic from the `ai_brain` UI MUST route through
`/ai_brain/chat` → orchestrator. The vendor route `/llm/thread/generate` MUST
remain functional for non-ai_brain consumers (other vendor modules, any
downstream integrator using `llm_thread` directly).

**Verification:** `task_014_chat_routes_through_orchestrator`
- POST `/ai_brain/chat` returns 200 and forwards JWT-validated request to orchestrator
- ai_brain JS exclusively calls `/ai_brain/chat` (no fallback to vendor route)
- GET `/llm/thread/generate` continues to return 200 for direct Odoo calls

---

### R2 — Classical `_inherit` backward compatibility with vendor

**Constraint:** After ai_brain classically extends `llm.thread` and
`mail.message`, all existing vendor consumers MUST continue to work:
- `env["llm.thread"].browse(id)` / `create({...})` / `search([...])` return
  correct records including the new ai_brain fields
- Vendor controller at `/llm/thread/generate` still returns 200
- Vendor OWL components (`llm_chat_container`, `llm_thread_header`) mount and
  render without JS console errors

**Verification:** `task_015_llm_thread_vendor_compat`
- Direct ORM call against `llm.thread` model succeeds after extension
- `/llm/thread/generate` endpoint continues to return 200
- `llm_assistant` header patches load and render correctly

---

### R3 — JWT mint and validate

**Constraint:** `/ai_brain/chat` mints a short-lived (≤5 min) JWT carrying
`user_id`, signed with `ORCH_JWT_SECRET` (CLAUDE.md Section E1). The
orchestrator MUST reject unsigned, tampered, or expired tokens before
processing any prompt.

**Verification:** `task_016_chat_jwt_mint_and_validate`
- Valid JWT → orchestrator 200
- Tampered JWT (modified payload) → 401
- Expired JWT (>5 min old) → 401
- Missing Authorization header → 401

---

### R4 — Context chip persistence (res_model / res_id)

**Constraint:** When the user navigates to a form view, `res_model` and
`res_id` are passed to `/ai_brain/chat` and persisted on the `llm.thread`
record. The system returns the same thread for the same `(user_id, res_model,
res_id)` tuple across sessions.

**Verification:** `task_017_context_chip_thread_persistence`
- Two requests with same `(user_id, res_model, res_id)` return same `thread_id`
- Switching `res_id` on the same `res_model` creates or resumes a different thread
- `llm.thread` record correctly stores `res_model` and `res_id` after creation

---

### R5 — Token accounting fields (present; enforcement deferred)

**Constraint:** Each `ai.message` row (`mail.message` extended) records
`token_count_input`, `token_count_output`, and `total_cost_usd` at write
time, populated from the LiteLLM response. Budget enforcement (per-user daily
50k tokens, per-tenant monthly $200 — CLAUDE.md Section D6) is DEFERRED to
M4 with its own risk register entry.

**Verification:** `task_018_token_accounting_fields_populated`
- After a `/ai_brain/chat` round trip, the corresponding `mail.message` row
  has non-null `token_count_input`, `token_count_output`, `total_cost_usd`
- Values are consistent with the LiteLLM response usage fields
- Budget enforcement is NOT verified in M3 (M4 scope)

---

## Cross-references

| ADR | Relationship |
|-----|-------------|
| ADR 0001 | Amended with M3 reconciliation note (this PR) |
| ADR 0006 | M3 follows the same risk-register → task → PR discipline established in M2 R1 |
| ADR 0009 | vkey scoping — orthogonal, no impact |
| ADR 0010 | api_key field restriction — orthogonal, no impact |
| ADR 0011 | LiteLLM DB persistence — M3 orchestrator `/chat` endpoint reuses the same LiteLLM instance |
| ADR 0012 | pydantic cold-start — M3 adds no new external Python deps to vendor modules |

---

## Consequences

**Positive:**
- M3 scope is bounded and reviewable: model layer (R2) + JWT (R3) + route
  intercept (R1) + context chip (R4) + token fields (R5). Five PRs at most.
- Architectural drift from ADR 0001 is corrected and documented.
- M4 entry criteria are explicit: γ-mid (history loading) then γ-thick
  (RAG + ReAct + tools), each with its own risk register.

**Acknowledged trade-offs:**
- M3 ships chat plumbing without agency. Demos show end-to-end JWT-validated
  streaming chat with no tool execution or RAG. This is an intentional cut;
  M4 closes the gap.
- The CLAUDE.md key-models table will become misleading until a follow-up
  erratum clarifies that `ai.conversation` and `ai.message` are extensions of
  vendor models, not standalone `_name` values. Tracked separately.

**Verification discipline:**
Each implementation PR must cite this ADR and the specific risk it closes.
The M3 closure PR (analogous to PR #9 for M2) will paste live evidence for
tasks 014–018 and record the final eval pass rate.
