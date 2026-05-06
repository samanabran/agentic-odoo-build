# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Read this file first, every session. All policies from the Master Addendum v1.0 are embedded inline below.

---

## Project overview

**Odoo AI Brain** — an AI layer for Odoo 19 Community. An in-app chat assistant that reads all records the logged-in user is permitted to see, drafts and (with approval) executes write actions, and converses via a side panel embedded in the Odoo web client.

Built on top of two existing foundations:
- **Odoo 19's native `productivity.ai`** — chat surface and base agent framework
- **Apexive `odoo-llm`** (submodule, 18.0 branch, SHA `1ede75911bd4565a7f544be06e31a651f9d63cf7`) — provider abstraction, `@llm_tool` decorator, MCP server, accounting tool pack

Full kickoff brief: `kickoff-odoo-ai-brain.html`. In case of conflict: this file > addendum > kickoff brief.

---

## Section A — Working method (apply every milestone)

**A1. Plan → code, never code → plan.**
At the start of every milestone produce a written plan: files to create/modify, new dependencies, exact commands, the test that proves acceptance. Wait for explicit approval before writing any code.

**A1. One milestone at a time.**
Never start the next milestone without explicit human approval. Never silently roll work from one milestone into another.

**A1. Conventional commits. Branch `m{N}-{slug}` per milestone.** Open a draft PR at the start; push commits as you go.

**A1. Tests before merge.** `make test` must be green. `make eval` must not regress vs main.

**A1. Merge strategy: Squash and merge.** Every PR lands as a single commit on `main`. This keeps the log readable and makes `git bisect` useful. Set in repo Settings → General → Pull Requests → Allow squash merging (only).

**A1. ADR for every non-obvious decision.** File in `docs/adr/`, numbered sequentially. Required when choosing between two or more reasonable options.

**A2. Secrets.** Never embed in code, config, commits, logs, or chat. All secrets in `.env` (gitignored), placeholders in `.env.example`. When a secret is needed: stop, name the variable and why, wait. Do not invent fake-but-valid-looking keys. gitleaks pre-commit hook blocks offending commits.

**A3. Docs in the same commit.** Update `docs/` in the same commit that introduces the change. `CLAUDE.md` is the canonical brief for future AI sessions — every policy lives here, not just linked from an ADR. `README.md` is the canonical brief for human developers.

**A4. Reversibility.** Every change must be revertable by `git revert`. No out-of-band file edits. No manual DB changes outside migration scripts. Every AI-initiated Odoo write carries the AI-origin mixin tags (see Section E).

**A5. When uncertain, stop and ask.** One focused question. Two reasonable approaches → one-paragraph ADR draft comparing them, ask which to choose. Never silently pick an option with architectural consequences.

**I3. Scope creep.** If during a milestone you discover additional work that feels related, stop, write a one-paragraph proposal naming it as a new milestone or follow-up issue, and continue with the originally approved scope.

---

## Section B — Repository manifest and vendor policy

### Tier 1 — Docker images (M1)
| Image | Service |
|---|---|
| `odoo:18.0` | odoo |
| `pgvector/pgvector:pg16` | db |
| `redis:7-alpine` | redis |
| `ghcr.io/berriai/litellm:main-stable` | litellm |
| `nginx:alpine` | nginx |
| `jaegertracing/all-in-one:latest` | jaeger |
| `ollama/ollama:latest` | ollama (private profile only) |

### Tier 2 — Odoo addons as git submodule (M2)
`addons/vendor/odoo-llm` → `apexive/odoo-llm`, pinned to SHA `1ede75911bd4565a7f544be06e31a651f9d63cf7` (18.0 branch, 2026-05-01).

Modules to install in order: `llm`, `llm_thread`, `llm_tool`, `llm_assistant`, `llm_openai`, `llm_ollama`, `llm_pgvector`, `llm_knowledge`, `llm_tool_knowledge`.
Install but disable until later: `llm_mcp_server` (enable M7), `llm_tool_account` (enable M7).

### Tier 3 — Python packages (`/orchestrator/pyproject.toml`, M1)
`fastapi`, `uvicorn`, `pydantic>=2`, `httpx`, `redis`, `structlog`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `prometheus-client`, `langgraph`, `langchain-core`, `pyjwt`, `python-jose`, `pyyaml`, `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`

### Tier 4 — Reference reading only, never vendored
`tuanle96/mcp-odoo`, `modelcontextprotocol/servers`, `MFYDev/odoo-expert`, `asyntai/odoo-ai-chatbot`, `OCA/queue`, `OCA/server-tools`. May read for inspiration. Do NOT copy code without an explicit ADR and license check.

### B2. Vendor diff policy — ZERO tolerance
The diff between `addons/vendor/odoo-llm` and the pinned commit SHA must be zero at all times:
```bash
git -C addons/vendor/odoo-llm diff --quiet HEAD
```
If a change is needed in vendor code: (1) override from `ai_brain`, (2) open upstream PR, (3) fork to `addons/vendor/odoo-llm-fork` as last resort with its own ADR. **Never patch vendor files in place.**

### B3. Submodule updates
SHA changes require an ADR update (0002) and a "vendor bump" PR separate from feature work. CI must run `make eval` before the bump merges.

---

## Section C — Odoo version (locked)

**Odoo 18 Community Edition** (`odoo:18.0`). Downgraded from Odoo 19 on 2026-05-06 after M2 spike confirmed hard version-check block (ADR 0006). See ADR 0007 for image digest pin.

Original Odoo 19 rollback has been executed. See ADR 0006 (spike) and ADR 0007 (image pin) for details. To upgrade back to Odoo 19: update docker-compose image, manifest prefix, and vendor pin once Apexive publishes a 19.0 branch.

---

## Section D — LLM providers and routing

### D1. Provider matrix
| Role | Provider | Virtual model name |
|---|---|---|
| Cloud default (production) | Anthropic claude-haiku-4-5-20251001 | `prod-default` |
| Cloud alternate (production) | OpenAI gpt-4o-mini | `prod-alternate` |
| Private mode (production) | Ollama qwen2.5:7b | `prod-local` |
| Development default | GitHub Models gpt-4o-mini | `github-dev` |
| Eval harness default | GitHub Models gpt-4o-mini | `github-dev` |

### D2. LiteLLM is the only entry point
The orchestrator NEVER calls a provider SDK directly. It calls the LiteLLM service. All four virtual models are defined in `infra/litellm/config.yaml`. Routing logic lives in the orchestrator, not in LiteLLM.

### D3. Routing rules (enforced in `app/main.py::get_active_model()`, tested)
```
PRIVATE_MODE=true         → prod-local
ENVIRONMENT=production    → prod-default
ENVIRONMENT=development   → github-dev
anything else             → RuntimeError (refuse to start)
```

### D4. Production guard (hard failure, not a warning)
`_assert_no_github_models_in_production()` runs in the lifespan hook. If `ENVIRONMENT=production` and `DEFAULT_MODEL` references a `github/*` endpoint → `RuntimeError`. Non-fatal warning logged if `GITHUB_TOKEN` is set in production.

### D5. GitHub Models endpoint
Canonical: `https://models.github.ai/inference`. The legacy `https://models.inference.ai.azure.com` URL is deprecated — do not introduce it in new code.

### D6. Cost controls (enforced from M4)
- Per-user daily token budget: 50k tokens/day (configurable via `USER_DAILY_BUDGET_TOKENS`), stored in Redis.
- Per-tenant monthly USD budget: $200/month (configurable via `TENANT_MONTHLY_BUDGET_USD`). Warning at 80%, hard block at 100%.
- Token usage and estimated cost logged to `ai.tool.log` for every call.
- `/admin/usage` endpoint on the orchestrator exposes consumption per user and tenant.
- Tracking is live from M1; enforcement is wired in M4 when auth context is available.

### D7. GitHub Copilot — explicit prohibition
The Copilot subscription is for developer IDE assistance only. The deployed system MUST NOT call Copilot endpoints. Do not integrate, document, or recommend any tool that exposes Copilot as an OpenAI-compatible API. This applies to all environments including local development.

---

## Section E — Security, audit, and approval

### E1. Auth chain
Odoo issues a short-lived (5 min) signed JWT when the chat panel calls the orchestrator. The orchestrator validates the JWT, extracts `user_id`, and calls Odoo JSON-RPC AS THAT USER. No service account, no super-user backdoor.

### E2. Tool registration contract
Every tool must declare: `name`, `description`, `input_schema` (JSON Schema, strict — reject extra fields), `output_schema`, `required_groups`, `requires_approval`, `side_effects` (`none|read|write|external`), `rate_limit`.

### E3. Approval flow
Tools with `side_effects` in `{write, external}` OR `requires_approval=true` must pause and surface an Approve/Reject card in the chat UI. Write tools must never execute without approval.

### E4. Audit log `ai.tool.log` — mandatory, append-only
Every tool call writes: `tool_name`, `args_json`, `result_json` (truncated if huge, full hash always), `success`, `latency_ms`, `tokens_in`, `tokens_out`, `est_cost_usd`, `user_id`, `conversation_id`, `message_id`, `approved_by`, `origin_ip`, `model_used`. No tool may delete or modify entries. Kanban view for admins.

### E5. AI-origin tagging (`ai.origin.mixin`)
Every Odoo record created or modified by AI must inherit `ai.origin.mixin` and carry:
- `x_ai_origin_conversation_id` (Char, indexed)
- `x_ai_origin_message_id` (Char, indexed)
- `x_ai_created_at` (Datetime)

Server action "Revert AI changes from conversation X" implemented in M4.

### E6. Field redaction
`orchestrator/app/security/redaction.py` loads `infra/redaction.yaml`. Sensitive fields stripped from every record payload before it leaves the orchestrator for an external LLM. Does NOT run for `prod-local` routes. Tests must verify redacted fields never appear in outbound prompts (M6).

### E7. Prompt injection defense
All record-derived text is wrapped in `<untrusted>...</untrusted>` before being inserted into the LLM context. The system prompt instructs the model to ignore instructions inside `<untrusted>` blocks. A regression test set of known injection strings runs in `make eval` (M6).

### E8. Rate limits
Per user, per tool, per minute. Stored in Redis. Defaults: 30 calls/min for read tools, 10 calls/min for write tools. 429 response shows a non-alarming message in the chat UI.

---

## Section F — Local development experience

### F2. Ollama is optional
`make up` starts 6 services (db, redis, odoo, orchestrator, litellm, nginx, jaeger). Ollama is under the `private` Docker Compose profile.
`make up-private` adds Ollama. Required when `PRIVATE_MODE=true`.

### F3. Hot reload
Orchestrator runs `uvicorn --reload`. Odoo runs with `--dev=xml` and the addons folder mounted as a volume.

### F5. Canonical Make targets
| Target | Action |
|---|---|
| `make up` | Start core stack |
| `make up-private` | Start core stack + Ollama |
| `make down` | Stop everything |
| `make logs` | Tail all logs |
| `make shell-odoo` | Shell into Odoo container |
| `make shell-orch` | Shell into orchestrator container |
| `make test` | Run all tests |
| `make eval` | Run eval harness against github-dev |
| `make seed` | Load demo data |
| `make reindex` | Rebuild ai.knowledge.chunk |
| `make lint` | Run ruff + mypy |

---

## Section G — Observability

**G1.** All orchestrator logs are JSON via structlog. Required fields: `timestamp`, `level`, `service`, `request_id`, `user_id` (if auth), `conversation_id` (if any), `event`.

**G2.** OpenTelemetry tracing via OTLP HTTP to Jaeger (`http://jaeger:4318`). Jaeger UI at `http://localhost:16686`. Manual spans required around: LLM call, tool execution, JSON-RPC call to Odoo, redaction, RAG retrieval.

**G3.** Prometheus `/metrics` on the orchestrator. Required metrics: `llm_requests_total`, `llm_tokens_total`, `llm_cost_usd_total`, `tool_calls_total`, `tool_latency_seconds`, `rag_queries_total`, `rag_latency_seconds`. Grafana dashboard JSON: `infra/grafana/dashboard.json` (populated M8).

---

## Section H — Evaluation harness

**H1.** `orchestrator/eval/` with `runner.py` and `tasks/task_*.py`. `make eval` runs all tasks against `github-dev`. Skips are not failures.

**H2. Grows each milestone:**
M1: 3 tasks (liveness, routing, LLM echo) | M2: +5 | M3: +5 | M4: +10 | M5: +10 | M6: +10 | M7: +10 | M8: dashboard + CI regression

**H3.** A milestone PR cannot merge if eval pass rate drops vs main. Degradation must be justified in the PR description.

---

## Section I — Milestone guardrails

### I1. Definition of done (every milestone)
- [ ] Code matches approved plan; no scope creep
- [ ] All new behavior covered by tests
- [ ] `make test` green
- [ ] `make eval` green, not regressed
- [ ] `make lint` green
- [ ] Docs updated in the same PR
- [ ] Manual smoke test recorded in PR description
- [ ] Observability in place for new behavior
- [ ] Vendor diff is zero
- [ ] No secrets leaked (gitleaks + CI scan)
- [ ] Human approver has reviewed and approved

### I2. End-of-milestone summary (mandatory format)
```
Milestone Mn — <name>
Status: complete / blocked / needs decision
Files changed: <list>
New deps: <list>
Tests added: <count>, eval tasks added: <count>
ADRs added: <list>
Smoke test command(s) run: <list>
Smoke test result: <pass/fail with output>
Known issues: <list or "none">
Next milestone unblocked? yes/no, why
```

---

## Tech stack

| Layer | Choice |
|---|---|
| ERP | Odoo 19 Community (`odoo:19.0`) |
| Database | PostgreSQL 16 + pgvector |
| Backend | Python 3.11, FastAPI orchestrator |
| Cache / queues | Redis |
| LLM gateway | LiteLLM sidecar |
| LLM providers | Anthropic (primary), OpenAI (alternate), Ollama (private) |
| Embeddings | `text-embedding-3-small` (cloud), `bge-m3` (local) |
| Frontend | Odoo OWL 2 framework |
| Tracing | OpenTelemetry → Jaeger |
| Metrics | Prometheus + Grafana |
| Dev infra | Docker Compose |
| Prod infra | Helm chart skeleton (M9) |

## Vendor compatibility (Odoo 19)

Apexive's `odoo-llm` has no 19.0 branch (pinned to 18.0 SHA). Vendor diff must be zero — no patching in place. Override via `ai_brain` Odoo inheritance or, as last resort, fork with ADR. Known 18→19 delta is incremental (not structural). See ADR 0002 and ADR 0004.

## Key models in `ai_brain`

| Model | Purpose | Milestone |
|---|---|---|
| `ai.origin.mixin` | Tags AI-written records for audit/revert | M1 scaffold |
| `ai.conversation` | Per-user chat sessions | M3 |
| `ai.message` | Individual messages with token counts | M3 |
| `ai.tool.log` | Append-only audit trail | M4 |
| `ai.policy` | Per-model write permissions, redaction config | M4 |
| `ai.knowledge.chunk` | Vectorized record embeddings | M5 |

## Non-negotiables

1. AI never has more privilege than the acting user — JWT auth chain only
2. Medium/high-impact write actions require explicit user approval
3. Every AI read/write is recorded in `ai.tool.log`
4. Sensitive fields redacted before leaving orchestrator for external LLM
5. `PRIVATE_MODE=true` forces Ollama — all external LLM calls disabled
6. Record-derived text wrapped in `<untrusted>` delimiters in system prompt
7. GitHub Copilot endpoints never called by the deployed system

## Environment variables (key ones)

See `.env.example` for the full list. Critical variables:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` or `production` — controls routing |
| `PRIVATE_MODE` | `true` forces prod-local (Ollama); overrides ENVIRONMENT |
| `ORCH_JWT_SECRET` | Signs orchestrator JWTs — generate with `openssl rand -hex 32` |
| `ANTHROPIC_API_KEY` | Required in production |
| `GITHUB_TOKEN` | Required in development / eval harness |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://jaeger:4318` in dev |

## Build milestones (M1–M9)

See `kickoff-odoo-ai-brain.html` for acceptance criteria per milestone. Never start a new milestone without explicit human "approved, proceed with MN".
