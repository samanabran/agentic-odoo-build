# Session State — 2026-05-12

## Branch
`chore/commit-all-changes-main`

## Verified Working

### Orchestrator quality gates
- `pytest tests -q` → 29 passed, 0 failed
- `ruff check app eval tests` → all checks passed
- `mypy app --ignore-missing-imports` → success

### M3 conversation layer
- Odoo `/ai_brain/chat` controller implemented and JWT-forwarding is active
- Orchestrator `/chat` endpoint validates JWT and routes via LiteLLM
- `ai.conversation` and `ai.message` models are present

### M4 finance-first implementation (substantially complete in code)
- U1 models present:
	- `ai.reconciliation.session`
	- `ai.reconciliation.suggestion`
	- `ai.aml.alert`
- U2 deterministic engine present:
	- `addons/ai_brain/services/matching_engine.py`
- U3 tools model present:
	- `addons/ai_brain/models/ai_brain_finance.py`
	- methods: `suggest_bank_reconciliation`, `generate_reconciliation_report`, `check_aml_patterns`
- U4 tools endpoint present:
	- `orchestrator/app/api/tools.py` (`POST /tools/narrative`)
- U5 dashboard present:
	- `addons/ai_brain/controllers/dashboard.py`
	- `addons/ai_brain/templates/dashboard.xml`
- U6 tests/eval tasks present for finance/dashboard/narrative paths

### Syntax/config integrity restored
- No merge-conflict markers remain in active source/config files
- Python compile checks pass for key `addons/ai_brain` files
- `infra/litellm/config.yaml` parses successfully as YAML

---

## Pending / Next Work

### 1) Environment-backed validation still pending
- `make eval` currently reports mostly `SKIP` because local services and required env vars are not fully provisioned in this shell context.
- Required for meaningful end-to-end validation:
	- Odoo + orchestrator + LiteLLM running
	- `ODOO_ADMIN_PASS`, `ORCH_JWT_SECRET`, and LiteLLM key env vars set

### Current execution blockers (observed today)
- Docker daemon unavailable on this host shell (`dockerDesktopLinuxEngine` pipe missing), so compose stack cannot start.
- `.env` readiness check:
	- `ORCH_JWT_SECRET`: set
	- `LITELLM_VKEY_CLOUD_DEV`: set
	- `ODOO_ADMIN_PASS`: missing
	- `LITELLM_MASTER_KEY`: missing

### 2) Documentation alignment
- `README.md` still contains stale references (for example Odoo 19 wording and outdated command list) and should be synchronized with the current Odoo 18 + Makefile reality.

### 3) Admin usage endpoint hardening
- `/admin/usage` is now Redis-backed and returns live counters with budget limits.
- Future enhancement: replace temporary `anonymous` user key with authenticated actor/tenant context.

### 4) Security hygiene (user action)
- Rotate any credentials previously exposed in chat/session history.
- Store fresh credentials in `.env` only.

---

## Session Update — 2026-05-13

### Completed in this run
- Vendor submodule B2 violation resolved: reset `addons/vendor/odoo-llm` to pinned SHA `1ede75911` (was drifted to `c5c99465`)
- `orchestrator/eval/runner.py` fixed: auto-loads `.env` via python-dotenv and reconfigures stdout to UTF-8 (Windows cp1252 crash fix)
- Eval now runs natively via `python -m eval.runner` with no shell setup required

### Eval results (2026-05-13)
- **31 unit tests passed, 0 failed**
- **15 eval tasks passed, 3 skipped, 0 failed** (up from 2 passed / 16 skipped)
- Remaining skips:
  - `task_006_ollama_echo` — intentional (PRIVATE_MODE not active)
  - `task_aml_check` — runtime exception from Odoo call
  - `task_narrative_quality` — `/tools/narrative` endpoint returns 500

### Final eval (2026-05-13 after all fixes)
- **17 passed, 1 skipped, 0 failed**
- Only skip: `task_006_ollama_echo` — intentional (PRIVATE_MODE not active)

### Next actions
- README.md alignment (stale Odoo 19 references)

---

## Session Update — 2026-05-12 (Later)

### Completed in this run
- Docker Desktop started and compose stack is up (`db`, `redis`, `odoo`, `orchestrator`, `litellm`, `nginx`, `jaeger`).
- Playwright MCP validation completed:
  - `http://localhost:8088/health` returns `{"status":"ok","version":"0.1.0"}`
  - Odoo DB selector is reachable and navigation to `ai_brain_dev` login page works.
- `LITELLM_MASTER_KEY` added to `.env` and LiteLLM/orchestrator services reloaded.

### Current prerequisite status
- `ORCH_JWT_SECRET`: set
- `LITELLM_MASTER_KEY`: set
- `LITELLM_VKEY_CLOUD_DEV`: set
- `ODOO_ADMIN_PASS`: missing

### Eval status after this run
- `3 passed, 15 skipped, 0 failed`
- Remaining skips are primarily due to missing `ODOO_ADMIN_PASS` and unstable/downstream LiteLLM task conditions.

---

## Key Notes

### Routing rules
```
PRIVATE_MODE=true       -> prod-local
ENVIRONMENT=production  -> prod-default
ENVIRONMENT=development -> github-dev
```

### Finance heuristics currently implemented
- Structuring band: 85% to 99% of threshold
- Round-number detection: multiples of 1000 with minimum count gate
- High-frequency detection: >10 transactions in 24h window

### Make targets used for validation
```
make test
make lint
make eval
```
