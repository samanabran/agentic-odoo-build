# Runbook

> Skeleton — to be completed in M9.

## Scenarios to be documented

- Provider outage (OpenAI/Anthropic down): fail over to alternate provider in LiteLLM config
- Rate-limit storm: Redis TTL keys, per-user limits, how to reset
- Bad prompt template: how to identify and roll back a system prompt change
- Vector store rebuild: running `scripts/reindex.py` safely
- Backup and restore: Postgres dump covers both relational data and pgvector embeddings
