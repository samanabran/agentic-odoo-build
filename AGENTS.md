# AGENTS.md — Odoo AI Brain

> Quick-start for AI coding agents. Full policies in [CLAUDE.md](CLAUDE.md). Architecture detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Build & test commands

```bash
make up            # start all services (Docker Compose)
make up-private    # + Ollama (PRIVATE_MODE)
make test          # pytest with coverage (cd orchestrator first)
make lint          # ruff + mypy
make eval          # golden-task eval harness
make down          # stop everything
```

Tests live in `orchestrator/tests/`. Coverage target: **80% minimum**.

## Project layout

```
addons/ai_brain/       Odoo 18 module (OWL frontend + Python models)
addons/vendor/         git submodule — apexive/odoo-llm (pinned SHA, never patch in-place)
orchestrator/app/      FastAPI orchestrator (Python 3.11)
infra/                 docker-compose, LiteLLM config, nginx
docs/adr/              Architecture Decision Records (numbered, read before changing architecture)
```

## Stack essentials

| Layer | Tech |
|---|---|
| ERP | Odoo 18 Community (`odoo:18.0`) |
| Orchestrator | Python 3.11 · FastAPI · LangGraph · LiteLLM |
| DB | PostgreSQL 16 + pgvector |
| Cache | Redis |
| LLM gateway | LiteLLM sidecar (single entry point — never call provider SDKs directly) |
| Frontend | Odoo OWL 2 |

## Critical non-negotiables (violations = blocked PR)

1. **Vendor diff must be zero.** Never edit files under `addons/vendor/`. Override via `ai_brain` inheritance or open an upstream PR. Check: `git -C addons/vendor/odoo-llm diff --quiet HEAD`.
2. **No secrets in code.** All secrets in `.env` (gitignored). Placeholders in `.env.example` only.
3. **JWT auth only.** Orchestrator calls Odoo as the acting user — no service-account backdoor.
4. **Write actions require approval.** Any tool with `side_effects in {write, external}` must surface an Approve/Reject card before executing.
5. **Append-only audit log.** Every tool call writes to `ai.tool.log`. No deletes or updates.
6. **GitHub Copilot endpoints are prohibited at runtime.** Development IDE usage is fine; deployed system must never call Copilot APIs.

## LLM routing rules (enforced in `orchestrator/app/main.py`)

```
PRIVATE_MODE=true         → prod-local  (Ollama, no external calls)
ENVIRONMENT=production    → prod-default (Anthropic claude-haiku)
ENVIRONMENT=development   → github-dev  (GitHub Models gpt-4o-mini)
anything else             → RuntimeError (startup fails)
```

Production startup hard-fails if `DEFAULT_MODEL` references a `github/*` endpoint — this is intentional.

## Key models to know

| Model | File | Purpose |
|---|---|---|
| `ai.origin.mixin` | `addons/ai_brain/models/ai_origin_mixin.py` | Tags every AI-written Odoo record |
| `ai.conversation` | (M3) | Per-user chat sessions |
| `ai.message` | (M3) | Individual messages with token counts |
| `ai.tool.log` | (M4) | Append-only audit trail |
| `ai.knowledge.chunk` | (M5) | Vectorised record embeddings |

## Odoo 18 conventions

- Module version prefix: `18.0.x.y.z`
- Field names follow Odoo ORM conventions; use `fields.Date.today()` (not `fields.date.today()`)
- AI-origin records must inherit `ai.origin.mixin` and carry `x_ai_origin_conversation_id`, `x_ai_origin_message_id`, `x_ai_created_at`
- Sensitive fields stripped via `orchestrator/app/security/redaction.py` + `infra/redaction.yaml` before any external LLM call

## Orchestrator conventions

- All logs are JSON via `structlog`; required fields: `timestamp`, `level`, `service`, `request_id`, `user_id`, `conversation_id`, `event`
- OpenTelemetry spans required around: LLM call, tool execution, Odoo JSON-RPC call, redaction, RAG retrieval
- Prometheus metrics declared in `main.py` at module level; see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full list
- Eval tasks live in `orchestrator/eval/tasks/`; add new ones alongside each milestone

## Environment variables (minimum to run)

```
ENVIRONMENT=development        # or production
ORCH_JWT_SECRET=<openssl rand -hex 32>
GITHUB_TOKEN=ghp_...           # for make eval / development LLM
```

Full list: `.env.example`

## ADRs — read before architectural changes

- [0001](docs/adr/0001-stack-choice.md) Stack choices
- [0002](docs/adr/0002-vendor-pinning.md) Vendor pinning policy
- [0003](docs/adr/0003-github-models-dev-only.md) GitHub Models dev-only policy
- [0004](docs/adr/0004-odoo-version-decision.md) Odoo version decision (downgraded to 18)
- [0005](docs/adr/0005-version-locked.md) Version lock rationale
