# ADR 0005 — Version Lock

**Date:** 2026-05-06
**Status:** Accepted

## Decision

| Component | Version |
|---|---|
| Odoo | 18 Community (`odoo@sha256:b79d87a4ec1a3806d133e12a07dc06402fc37397eb285663b1acfea2001ae52c`) |
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
---

## Rollback record — 2026-05-06

Rollback executed per step 3 of the rollback plan above.

**Trigger:** M2 spike (ADR 0006) confirmed Odoo 19 rejects all 18.0.x vendor
modules via a hard check_version() block. No override path exists within the
B2 zero-diff constraint.

**Changes applied (single commit on chore/rollback-to-odoo-18):**
- infra/docker-compose.yml: odoo:19.0 → pinned digest (ADR 0007)
- ddons/ai_brain/__manifest__.py: 19.0.1.0.0 → 18.0.1.0.0
- All non-vendor 19.0 references swept to 18.0
- M1 gates re-run against odoo:18.0 — all green

**M1 gate results post-rollback:** see PR description on chore/rollback-to-odoo-18.