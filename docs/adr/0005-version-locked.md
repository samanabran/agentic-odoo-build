# ADR 0005 — Version Lock

**Date:** 2026-05-06
**Status:** Accepted

## Decision

| Component | Version |
|---|---|
| Odoo | 19 Community (`odoo:19.0` Docker image) |
| PostgreSQL | 16 (`pgvector/pgvector:pg16`) |
| pgvector | bundled with pg16 image |
| Python | 3.11 (orchestrator) |
| Apexive odoo-llm | `18.0` branch, SHA `1ede75911bd4565a7f544be06e31a651f9d63cf7` |

## Rollback plan

If a hard blocker is discovered against Odoo 19 in M2 (i.e., a vendor module
cannot be made to work via `ai_brain` overrides AND upstream is unwilling to
accept a PR AND a fork is unacceptable), the fallback is:

1. Change `odoo` image in `docker-compose.yml` from `odoo:19.0` to `odoo:18.0`.
2. Update `addons/ai_brain/__manifest__.py` version prefix from `19.0` to `18.0`.
3. Update this ADR to reflect the downgrade.
4. Notify the project owner; document the blocking issue and the 19.0 upgrade plan.

The rollback is a one-commit change and does not affect the orchestrator,
LiteLLM, Redis, or any infrastructure outside the Odoo container.
