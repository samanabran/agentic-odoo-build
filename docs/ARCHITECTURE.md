# Architecture

> Skeleton — to be completed in M9. See `docs/adr/` for individual decisions.

## System overview

```
Browser (Odoo Web Client + AI Chat Panel)
        │ WebSocket / JSON-RPC
Odoo 18 (OWL frontend · ORM · PostgreSQL)
  ├── productivity.ai (native AI app)
  ├── odoo-llm vendor modules
  └── ai_brain (our module: chat widget, audit, approval)
        │ HTTPS + signed JWT
FastAPI Orchestrator
  ├── LangGraph planning loop (ReAct, max 8 steps)
  ├── LiteLLM gateway → OpenAI / Anthropic / Ollama
  ├── Tool executor → Odoo JSON-RPC as the acting user
  └── Redaction + guardrails layer
        │
PostgreSQL 16 + pgvector   Redis   Ollama (PRIVATE_MODE)
```

## Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `odoo` | `odoo:18.0` | 8069 | ERP + chat surface |
| `orchestrator` | local build | 8088 | FastAPI LLM orchestrator |
| `litellm` | `ghcr.io/berriai/litellm:main-stable` | 4000 | LLM gateway |
| `db` | `pgvector/pgvector:pg16` | 5432 | Postgres + vector store |
| `redis` | `redis:7-alpine` | 6379 | Sessions, rate limits, queues |
| `ollama` | `ollama/ollama:latest` | 11434 | Local LLM (PRIVATE_MODE) |
| `nginx` | `nginx:alpine` | 80 | Reverse proxy |
