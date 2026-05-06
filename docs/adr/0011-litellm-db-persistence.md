# ADR 0011 — LiteLLM Database Persistence for Virtual Key Storage

**Status:** Accepted  
**Date:** 2026-05-07  
**Deciders:** samanabran  

---

## Context

ADR 0009 specifies that LiteLLM virtual keys are scoped per model (`github-dev` for cloud-dev, `prod-local` for local). The provisioning script (`scripts/provision_litellm_keys.sh`) calls `POST /key/generate` to create and store these keys.

However, LiteLLM was configured without a database backend, making it fully stateless. In this state:
- `GET /health/readiness` returns `"db": "Not connected"`
- `POST /key/generate` fails — there is nowhere to persist key metadata or model allowlists
- Tasks 009–013 (added for M2 R1 verification) have run only in **skip mode** because `LITELLM_VKEY_CLOUD_DEV` was never populated
- ADR 0009's claim that task_013 proves vkey scoping was therefore theoretical, not observed

This PR closes that gap.

---

## Decision

**Colocate a `litellm` database on the existing pgvector/PostgreSQL container.**

- `infra/postgres/init.sql` appends `CREATE DATABASE litellm OWNER odoo;` so the database is created at first container boot.
- `infra/docker-compose.yml` litellm service receives:
  - `DATABASE_URL`: points at `postgresql://odoo:odoo@db:5432/litellm`
  - `LITELLM_SALT_KEY`: 64-char hex secret for at-rest encryption of stored virtual keys
  - `STORE_MODEL_IN_DB: "True"`: tells LiteLLM to persist model routing in the DB (not only config.yaml)
  - `depends_on: db: condition: service_healthy`: ensures Postgres is ready before LiteLLM starts
- `Makefile` COMPOSE variable gains `--env-file .env` so all `make` targets pick up the salt key and master key without manual export.
- `.env.example` documents `LITELLM_SALT_KEY` immediately after `LITELLM_MASTER_KEY`.

### Alternatives rejected

| Option | Reason rejected |
|--------|----------------|
| Separate Postgres container for LiteLLM | Doubles DB footprint for dev; unnecessary complexity |
| Redis for key storage | LiteLLM's Redis adapter only caches, does not persist `/key/generate` records |
| SQLite | Not available in the `ghcr.io/berriai/litellm:main-stable` container without volume mount complexity |

---

## Consequences

- **One-time destructive:** existing dev volumes must be destroyed (`docker compose down -v`) for the new `CREATE DATABASE` to execute via `initdb`. Existing databases (Odoo `ai_brain_dev` or `spike_test`) are lost; they will be recreated on first Odoo boot.
- **Second DB on shared Postgres:** acceptable for dev. For production, a dedicated Postgres instance or separate volume is recommended — add to ADR 0012 when production infra is designed.
- **Salt key rotation:** changing `LITELLM_SALT_KEY` invalidates all previously stored virtual keys. Re-run `scripts/provision_litellm_keys.sh` after any key rotation.
- **`LITELLM_MASTER_KEY` required:** LiteLLM will reject `/key/generate` requests if `LITELLM_MASTER_KEY` is blank. The `.env` file must have a non-empty value.

---

## Verification

After bringing the stack up with `make up`:

```bash
curl http://localhost:4000/health/readiness
# Expected: {"status":"healthy","db":"connected",...}

bash scripts/provision_litellm_keys.sh
grep LITELLM_VKEY .env
# Expected: both LITELLM_VKEY_CLOUD_DEV=sk-... and LITELLM_VKEY_LOCAL=sk-... non-empty

make eval
# Expected: tasks 009–013 run in PASS mode, not skip
```

---

## Cross-references

- [ADR 0009 — LiteLLM Virtual Key Scoping](0009-litellm-vkey-scoping.md): depends on this ADR for observed (not theoretical) proof
- [ADR 0010 — LLM Provider API Key Restriction](0010-llm-provider-api-key-restriction.md): companion R1 constraint
- `scripts/provision_litellm_keys.sh`: provisions `LITELLM_VKEY_CLOUD_DEV` and `LITELLM_VKEY_LOCAL`
- `orchestrator/eval/tasks/task_013_litellm_vkey_scoped_to_github_dev.py`: live verification of model scoping
