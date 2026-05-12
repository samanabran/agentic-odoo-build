# Session State — 2026-05-12

## Branch
`m3-r1-route-intercept` (2 commits ahead of `main`)

## What Is Done

### M3 — Conversation Layer (merged to main via squash)
- `ai.conversation` + `ai.message` models with classical inheritance hooks
- JWT plumbing: orchestrator `/chat` + Odoo `/ai_brain/chat`
- ADR 0013 (conversation architecture)

### M3-R1 — Route Intercept (on current branch, not yet PR'd)
| Commit | Content |
|---|---|
| `f0b4d68` | Route intercept controller, `/ai_brain/gate` endpoint, `addons/vendor/_rfs.scss` fix (Bootstrap vendor/rfs SCSS error) |
| `66a29b9` | Premium glassmorphism login CSS + QWeb template override, LiteLLM fallback model groups in `config.yaml` |

**Files changed vs main (14 files, +1065 lines):**
- `addons/ai_brain/controllers/ai_brain_thread.py` — route intercept
- `addons/ai_brain/static/src/css/auth.css` — glassmorphism login
- `addons/ai_brain/views/auth_templates.xml` — QWeb login template override
- `addons/ai_brain/tests/test_route_intercept.py` — route intercept tests
- `addons/vendor/_rfs.scss` — Bootstrap RFS vendor fix
- `orchestrator/app/api/gate.py` — gate endpoint
- `orchestrator/tests/test_chat_gate.py` — gate tests
- `infra/litellm/config.yaml` — fallback model groups added
- `.env.example` — GROQ_API_KEY + MISTRAL_API_KEY placeholders

### M4 — Plan Written
Plan at `docs/plans/2026-05-12-001-feat-m4-financial-intelligence-tools-plan.md`

Scope (Finance-first; CRM deferred to M5):
- **U1** — Odoo models: `ai.reconciliation.session`, `ai.reconciliation.suggestion`, `ai.aml.alert`
- **U2** — `MatchingEngine` service in `addons/ai_brain/services/matching_engine.py`
- **U3** — `ai.brain.finance` model with `@llm_tool` methods: `suggest_bank_reconciliation`, `generate_reconciliation_report`, `check_aml_patterns`
- **U4** — Orchestrator `POST /tools/narrative` in `orchestrator/app/api/tools.py`
- **U5** — HTML dashboard controller at `/ai_brain/dashboard`
- **U6** — 5 eval tasks + unit tests

---

## Blocked / Pending (in order)

### 1. SECURITY — Rotate all exposed tokens (USER ACTION REQUIRED)
All keys shared in chat are treated as compromised. Revoke and regenerate each:

| Key | Where to revoke |
|---|---|
| GitHub PAT `ghp_ymUwE...` | github.com/settings/tokens |
| GitHub PAT `github_pat_11CAM3DDQ0...` | github.com/settings/tokens |
| Groq `gsk_OaCR7b...` | console.groq.com/keys |
| Mistral `lYFHz82e...` | console.mistral.ai/api-keys |
| Opencode Z `sk-3Whsq...` | your Opencode dashboard |

After generating fresh keys, add them to `.env` (never in chat or code).

### 2. LiteLLM config — wrong model name prefixes
In `infra/litellm/config.yaml`, GitHub Models routes need `openai/` prefix:
- `mistral-ai/Mistral-small` → `openai/mistral-ai/Mistral-small`
- `meta/Meta-Llama-3.1-8B-Instruct` → `openai/meta/Meta-Llama-3.1-8B-Instruct`

### 3. Orchestrator — missing auth header for LiteLLM
In `orchestrator/app/api/chat.py::_call_litellm()`, when `LITELLM_MASTER_KEY` is set the httpx POST must include `Authorization: Bearer <LITELLM_MASTER_KEY>`. Currently missing → 401 from LiteLLM.

### 4. Create + merge PR #13 for M3-R1 branch
Push `m3-r1-route-intercept`, open PR against `main`, squash-merge.
Required before creating `m4-*` branch.

### 5. Write ADR 0014 — matching engine approach
Required before M4 implementation starts (project policy A1).

### 6. Implement M4 (all 6 units)
See plan doc above.

### 7. M5 — CRM auto follow-up + sequence reminders (deferred)

---

## Key Technical Notes

### Odoo 18 QWeb login inheritance
- `inherit_id="web.login_layout"` priority=20
- Correct xpath: `//t[@t-call='web.frontend_layout']` (not `web.layout`)
- Use `t-out="0"` (not deprecated `t-raw`)

### LLM provider routing (Section D3)
```
PRIVATE_MODE=true       → prod-local (Ollama)
ENVIRONMENT=production  → prod-default (Anthropic claude-haiku-4-5)
ENVIRONMENT=development → github-dev (GitHub Models gpt-4o-mini)
```

### Deterministic matching engine (M4-U2)
- Amount tolerance ±0.01 (configurable)
- Date window ±7 days (configurable)
- Partner name fuzzy match via token-set ratio ≥80
- Reference Jaccard similarity
- Composite confidence score 0–100

### AML heuristics (M4-U3)
- Structuring: 85–99% of reporting threshold
- Round-number clustering: ≥3 transactions × 1,000 in 24h
- High-frequency: >10 transactions per partner in 24h

### `@llm_tool` vendor registration pattern
`llm_tool/models/llm_tool.py::_register_hook()` → `_scan_tool_decorators()` → `_sync_tools_to_db()` on every Odoo startup (raw SQL + advisory lock). New tools must have `decorator_model` and `decorator_method` fields.

---

## Untracked files (not in any PR yet)
- `TODO.html`
- `llm-test-suite.html`
- `ui-screenshot.png`
- `addons/website_sgctech_ai/` — new addon, scope TBD
- `docs/plans/` — M4 plan (commit with M4 branch)

---

## Make targets
```
make up          # Start core stack
make down        # Stop everything
make logs        # Tail all logs
make test        # Run tests
make eval        # Run eval harness
make lint        # ruff + mypy
make shell-odoo  # Shell into Odoo container
make shell-orch  # Shell into orchestrator container
```
