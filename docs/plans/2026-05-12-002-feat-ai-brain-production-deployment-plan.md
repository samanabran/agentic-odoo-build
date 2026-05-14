---
title: ai_brain Production Deployment — sgctech.ai (Odoo 19)
status: active
created: 2026-05-12
deepened: ~
origin: CLAUDE.md + live server inspection
---

# ai_brain Production Deployment Plan

## Problem Frame

`ai_brain` and the Apexive `odoo-llm` vendor suite are developed locally but not yet installed on the live `sgctech.ai` server (`odoo-prod`, Odoo 19.0, database `odoo19-sgc`). The goal is to deploy these addons, install them in the correct dependency order, configure a working LLM provider, and validate the installation end-to-end — without breaking the currently healthy production system.

## Scope

**In scope:**
- Updating `ai_brain` manifest version to `19.0.1.0.0`
- Deploying `addons/vendor/odoo-llm` modules and `addons/ai_brain` to production server
- Pre-flight validation on `odoo-test-v19` before touching production
- Installing all vendor + `ai_brain` modules in correct order on `odoo19-sgc`
- Configuring Anthropic API key and LLM provider in the production stack
- Smoke-testing the AI chat panel and audit log

**Out of scope:**
- Full LiteLLM sidecar deployment (M4+ scope)
- Orchestrator FastAPI service deployment
- pgvector embedding / RAG pipeline (M5)
- Any frontend OWL component beyond what `ai_brain` already ships

## Server Context

| Detail | Value |
|--------|-------|
| Host | `80.241.218.108` |
| Container | `odoo-prod` (Odoo 19.0) |
| Database | `odoo19-sgc` |
| DB container | `odoo-prod-db` (postgres:16) |
| Addons drop path | `/opt/odoo-prod/extra-addons/` → `/mnt/extra-addons` inside container |
| Config file | `/opt/odoo-prod/odoo-prod.conf` |
| Test container | `odoo-test-v19` (safe pre-flight target) |
| Currently installed vendor | None of `llm_*` present yet |
| Version prefix reality | `18.0.x` modules install on Odoo 19 (confirmed by `website_sgctech_ai`); `19.0.x` is cleaner |

## Decisions

**D1 — Manifest version: `19.0.1.0.0`**
Updating `ai_brain` from `18.0.1.0.0` to `19.0.1.0.0`. Odoo 19 does not hard-block `18.0` prefixes (confirmed live), but using the correct prefix avoids future upgrade friction and aligns with production Odoo version.

**D2 — Vendor modules are NOT patched**
Vendor diff must remain zero (CLAUDE.md Section B2). The `odoo-llm` submodule ships `18.0.x` versions — they install on Odoo 19. No manifest edits to vendor files.

**D3 — Pre-flight on odoo-test-v19 is mandatory**
All install steps are run on `odoo-test-v19` first. Only after a clean pre-flight do we proceed to `odoo-prod`. This is the reversibility gate.

**D4 — LLM provider for initial deployment: Anthropic claude-haiku-4-5**
Use `ANTHROPIC_API_KEY` set in the container environment. LiteLLM full integration is M4 scope; for this deployment, the `llm_openai`-compatible provider from `odoo-llm` points directly to Anthropic.

**D5 — Module install list**
Install in this exact order (respects dependency chain):
1. `llm`
2. `llm_thread`
3. `llm_tool`
4. `llm_assistant`
5. `llm_openai`
6. `llm_knowledge`
7. `llm_tool_knowledge`
8. `ai_brain`

Hold back (per CLAUDE.md Section B): `llm_mcp_server` (M7), `llm_tool_account` (M7), `llm_pgvector` (M5 — needs pgvector check first), `llm_ollama` (private mode only).

## Implementation Units

### U1 — Verify pgvector on production postgres

**File:** no code change; diagnostic only
**What:** Confirm `pgvector` extension is available on `odoo-prod-db`. If present, `llm_pgvector` can be added to the install list in M5. If absent, it stays excluded now.
**Command:**
```bash
docker exec odoo-prod-db psql -U odoo -d odoo19-sgc \
  -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```
**Test scenarios:**
- Returns one row `vector` → pgvector available, document for M5
- Returns zero rows → document as blocker for `llm_pgvector`; proceed without it

---

### U2 — Update ai_brain manifest version

**File:** `addons/ai_brain/__manifest__.py`
**What:** Change `"version": "18.0.1.0.0"` → `"version": "19.0.1.0.0"`. No other changes.
**Why:** Production is Odoo 19; matching the prefix is correct and avoids future upgrade warnings.
**Test scenario:** `python -c "import ast; m=ast.literal_eval(open('addons/ai_brain/__manifest__.py').read()); assert m['version']=='19.0.1.0.0'"` passes locally.

---

### U3 — Create rsync deployment script

**File:** `scripts/deploy_addons_to_prod.sh` (new)
**What:** Idempotent script that rsyncs `addons/vendor/odoo-llm` modules and `addons/ai_brain` to the production server's extra-addons directory. Accepts `-n` for dry-run. Does NOT restart Odoo (that is a separate explicit step).

**Modules to sync from vendor:**
`llm`, `llm_thread`, `llm_tool`, `llm_assistant`, `llm_openai`, `llm_knowledge`, `llm_tool_knowledge`

**Logic sketch (not implementation code):**
```
for each MODULE in the list above:
  rsync -avz --delete --exclude='.git' \
    addons/vendor/odoo-llm/<MODULE>/ \
    root@HOST:/opt/odoo-prod/extra-addons/<MODULE>/

rsync -avz --delete --exclude='.git' --exclude='__pycache__' \
  addons/ai_brain/ \
  root@HOST:/opt/odoo-prod/extra-addons/ai_brain/
```

**Test scenarios:**
- Dry-run (`-n`) prints transfer list without writing to server
- After real run, `ssh root@80.241.218.108 ls /opt/odoo-prod/extra-addons/` shows all 7 vendor modules + `ai_brain`
- Vendor diff assertion still clean: `git -C addons/vendor/odoo-llm diff --quiet HEAD` → exit 0

---

### U4 — Pre-flight install on odoo-test-v19

**File:** no code change; operational procedure
**What:** Install full module list on `odoo-test-v19` and its test database. Confirms no import errors, model registration failures, or view XML parse errors before touching production.

**Steps:**
1. Sync addons to `odoo-test-v19`'s extra-addons path (confirm path via `docker inspect odoo-test-v19`)
2. Run:
   ```bash
   docker exec odoo-test-v19 odoo \
     -d <test-db-name> \
     -i llm,llm_thread,llm_tool,llm_assistant,llm_openai,llm_knowledge,llm_tool_knowledge,ai_brain \
     --stop-after-init
   ```
3. Check exit code 0, zero `ERROR` lines in stdout

**Test scenarios:**
- Install command exits 0
- No `ERROR` or `Traceback` in Odoo log during install
- `SELECT name, state FROM ir_module_module WHERE name IN ('llm','ai_brain') ORDER BY name;` → both `installed`
- Navigate to test Odoo URL — no OWL lifecycle errors on partner list view

---

### U5 — Deploy addons to production server

**File:** `scripts/deploy_addons_to_prod.sh` (U3)
**What:** Run the deploy script against production. Dry-run first, review output, then real run.
**Pre-conditions:** U4 pre-flight passed cleanly; U2 manifest update committed.
**Test scenario:** All target directories present under `/opt/odoo-prod/extra-addons/` with correct file counts matching local source.

---

### U6 — Install vendor modules on production

**File:** no code change; operational procedure
**What:** Install `llm` through `llm_tool_knowledge` on `odoo19-sgc`.

**Command:**
```bash
docker exec odoo-prod odoo \
  -d odoo19-sgc \
  -i llm,llm_thread,llm_tool,llm_assistant,llm_openai,llm_knowledge,llm_tool_knowledge \
  --stop-after-init
docker restart odoo-prod
```

**Test scenarios:**
- Exit code 0, no ERROR lines
- `SELECT name, state FROM ir_module_module WHERE name LIKE 'llm%';` → all 7 rows `installed`
- `https://sgctech.ai/web/health` → HTTP 200 after restart

---

### U7 — Install ai_brain on production

**File:** no code change; operational procedure
**What:** Install `ai_brain` on `odoo19-sgc` after vendor modules are confirmed installed.

**Command:**
```bash
docker exec odoo-prod odoo \
  -d odoo19-sgc \
  -i ai_brain \
  --stop-after-init
docker restart odoo-prod
```

**Test scenarios:**
- Exit code 0
- `SELECT state FROM ir_module_module WHERE name='ai_brain';` → `installed`
- `https://sgctech.ai/web/health` → HTTP 200
- No OWL lifecycle errors on Partners, Customers, or Sales Orders list views
- `ai.tool.log` model accessible from Settings → Technical (dev mode)

---

### U8 — Configure LLM provider

**File:** `addons/ai_brain/data/llm_providers.xml` (existing)
**What:** Confirm the Anthropic provider data record is correctly structured so it's loaded automatically during `ai_brain` install (U7). Provider should point to `https://api.anthropic.com/v1` with model `claude-haiku-4-5-20251001`.

**Secret handling:** `ANTHROPIC_API_KEY` must be set as an environment variable on the `odoo-prod` container — via `/opt/odoo-prod/.env` or Docker run args. Never hardcode in XML.

**Verification command:**
```bash
git grep -n "ANTHROPIC\|api_key\|sk-" -- 'addons/**/*.xml' 'addons/**/*.py' 'addons/**/*.conf'
```
Must return zero results.

**Test scenarios:**
- `SELECT name, provider FROM llm_provider;` (or equivalent model) shows Anthropic entry
- `ANTHROPIC_API_KEY` absent from all committed files
- Provider test connection returns success (if `odoo-llm` exposes that button)

---

### U9 — Smoke test and validation

**File:** no code; validation checklist
**What:** End-to-end validation that the AI chat panel loads, responds, and logs correctly.

**Checklist:**
- [ ] `https://sgctech.ai/web/health` → HTTP 200
- [ ] No OWL errors on Partners list, Customers list, Sales Orders list
- [ ] AI chat panel loads (side panel or dedicated view from `ai_brain`)
- [ ] Sending a chat message returns an LLM response (not an error 500 or timeout)
- [ ] `ai.tool.log` record created for the interaction (Settings → Technical → AI Tool Log)
- [ ] `ai.conversation` record exists for the session
- [ ] `docker logs odoo-prod --tail 100` shows no Python tracebacks

---

## Dependencies and Sequencing

```
U1 (pgvector check) ─────────────────────────────→ document result only
U2 (manifest) ──────────────────────────────────→ required before U5
U3 (deploy script) ──┬──→ U4 (pre-flight gate)
                     └──→ U5 (deploy to prod)  ←─ requires U4 pass
                                                    U6 ← U5
                                                    U7 ← U6
                                                    U8 ← U7
                                                    U9 ← U8
```

U1 and (U2 + U3) can run in parallel. U4 is the mandatory gate before U5. All subsequent steps are serial.

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Odoo 19 import-time incompatibility in `odoo-llm` (18→19 API delta) | Medium | U4 pre-flight on test-v19 catches this |
| `pgvector` not available → `llm_pgvector` fails | Medium | U1 check; module excluded from install list |
| `ANTHROPIC_API_KEY` not set in container env | Low | U8/U9 smoke test catches 401; key set before U8 |
| Broken OWL view regression from module install | Low | U9 check; U4 pre-flight already validated |
| rsync `--delete` removes server-only files | Low | Script targets only named subdirs; dry-run first |
| `data/llm_providers.xml` references non-existent field | Medium | Review XML against installed `llm` model schema before U7 |

## Test File Paths

| Unit | Evidence location |
|------|------------------|
| U2 (manifest) | `addons/ai_brain/__manifest__.py` — assert `version == '19.0.1.0.0'` |
| U3 (script) | `scripts/deploy_addons_to_prod.sh` — dry-run output |
| U4 (pre-flight) | `odoo-test-v19` install log + psql query |
| U6 (vendor install) | psql `ir_module_module` on `odoo19-sgc` |
| U7 (ai_brain install) | psql `ir_module_module` on `odoo19-sgc` |
| U8 (provider) | `git grep` secret check + psql provider query |
| U9 (smoke test) | Manual checklist recorded in PR description |

## Reversibility

| Unit | Rollback |
|------|---------|
| U2 | `git revert` restores manifest |
| U3/U5 | rsync is idempotent; old files restored from git |
| U6 | Uninstall via Odoo UI (Settings → Apps) — cascade-safe if U7 not yet done |
| U7 | Uninstall `ai_brain` via Odoo UI before vendor modules |
| U8 | LLM provider record deletable via Odoo UI |

## Milestone Completion Criteria (CLAUDE.md I1)

- [ ] U2 manifest version updated and committed
- [ ] U3 deploy script created and dry-run verified
- [ ] U4 pre-flight passes on `odoo-test-v19`
- [ ] U5–U7 install succeeds on `odoo19-sgc`
- [ ] U8 provider configured, no secrets in code
- [ ] U9 smoke test checklist fully green
- [ ] `make test` green locally (no regressions)
- [ ] Vendor diff zero: `git -C addons/vendor/odoo-llm diff --quiet HEAD`
- [ ] `gitleaks` / CI secret scan clean

## Next Milestone Dependency

Once this deployment completes and U9 is green, M4 (tool approval flow, `ai.tool.log` enforcement, per-user cost budgeting) can begin. M4 requires `ai_brain` with its models live in `odoo19-sgc`.
