# Odoo AI Brain

An AI layer for Odoo 18 — in-app chat assistant with full audit trail, human-in-the-loop approval, and RAG over all permitted Odoo records.

Built on top of Odoo's native AI/chat surface and Apexive's `odoo-llm` framework.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- 8 GB RAM minimum; 16 GB recommended when running Ollama locally
- `openssl` available in your shell (for generating `ORCH_JWT_SECRET`)

## Quick start

```bash
# 1. Clone the repo
git clone <repo-url> odoo-ai-brain
cd odoo-ai-brain
git submodule update --init --recursive   # (after M2)

# 2. Configure
cp .env.example .env
# Edit .env — minimum: set ORCH_JWT_SECRET and at least one LLM provider key

# 3. Bootstrap (pulls images, starts services, enables pgvector)
bash scripts/bootstrap.sh

# 4. Open Odoo
#    http://localhost:8069  — create a database, install ai_brain module
#    http://localhost:8088/health — orchestrator health check
```

### Skip the Ollama model download

The default model (`qwen2.5:7b`) is ~4 GB. To skip it:

```bash
OLLAMA_SKIP_PULL=true bash scripts/bootstrap.sh
```

## Development commands

| Command | What it does |
|---|---|
| `make up` | Start all services in the background |
| `make down` | Stop all services |
| `make logs` | Tail all container logs |
| `make shell-odoo` | Shell into the Odoo container |
| `make shell-orch` | Shell into the orchestrator container |
| `make test` | Run the orchestrator test suite |
| `make eval` | Run the golden-task evaluation harness (M8) |
| `make bootstrap-pydantic` | Install missing Python deps in Odoo container (ADR 0012) |

## Project structure

```
addons/ai_brain/        Custom Odoo module
addons/vendor/          git submodule: apexive/odoo-llm (pinned)
orchestrator/           FastAPI orchestration service
infra/                  docker-compose, nginx, LiteLLM config
docs/                   Architecture docs, runbooks, ADRs
scripts/                Bootstrap, seed, and reindex scripts
```

## Milestones

See `kickoff-odoo-ai-brain.html` for the full 9-milestone build sequence and acceptance criteria.

## For developers

The team's GitHub Copilot subscription is used for **IDE coding assistance only** — autocomplete and Copilot Chat while you write code. The Odoo AI Brain system itself does **not** call GitHub Copilot at runtime; end-user chat traffic routes through LiteLLM to OpenAI, Anthropic, or Ollama. What the Copilot subscription *does* give you is an elevated GitHub Models API quota, which the development and evaluation harness (`make eval`) uses so you are not billed for test runs. To use it, add your personal token to `.env`:

```
GITHUB_TOKEN=ghp_...          # https://github.com/settings/tokens (read:org scope is enough)
ENVIRONMENT=development        # keeps the production guard from firing locally
```

The orchestrator will hard-error at startup if `ENVIRONMENT=production` and `DEFAULT_MODEL` references a GitHub endpoint — this is intentional and must not be bypassed. See `docs/adr/0003-github-models-dev-only.md` for rate limit details and the full policy rationale.

## Secrets

Never commit secrets. All keys go in `.env` (gitignored). When a new secret is required, add it to `.env.example` with an empty value and document the variable name in context.
