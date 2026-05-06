# ADR 0009 - LiteLLM Virtual Key Scoping (Constraint 1 of R1)

**Date:** 2026-05-07
**Status:** Accepted

## Context

Apexive's `llm_openai` module sends completions to whatever `api_base` and
`api_key` are stored on the `llm.provider` Odoo record. If the virtual key
were unrestricted, a misconfigured or injected model name could cause
LiteLLM to forward the request to a provider we did not intend — incurring
real cost and bypassing the routing rules in `app/main.py`.

The risk is labelled **R1** in the M2 discovery (ADR 0006) and its
verification plan covers three levels: gateway routing, bypass prevention,
and scope enforcement.

## Decision

The virtual key issued to the Odoo provider record (`LITELLM_VKEY_CLOUD_DEV`)
is scoped at key-generation time to **a single model alias: `github-dev`**.

Implemented in `scripts/provision_litellm_keys.sh`:

```bash
curl -sf -X POST \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"models":["github-dev"],"metadata":{"purpose":"apexive-cloud-dev"}}' \
  "${LITELLM_URL}/key/generate"
```

LiteLLM enforces the `models` allowlist at request time. Any call using
this key with a model name not in `["github-dev"]` receives a 4xx rejection
before the upstream provider is contacted.

## Consequences

- **Defense in depth:** even if Apexive's provider record is misconfigured
  or a prompt-injection attack attempts to change the model, the key cannot
  reach `prod-default`, `prod-local`, or any raw provider endpoint.
- **Re-provisioning:** running `scripts/provision_litellm_keys.sh` again
  regenerates the key with the same `models` scope. The old key is
  invalidated by LiteLLM on re-generation.
- **Eval coverage:** `task_013_litellm_vkey_scoped_to_github_dev` verifies
  both the allowed path (`github-dev` → 200) and the blocked path
  (`prod-local` → 4xx) on every `make eval` run.

## Alternatives rejected

- **Unrestricted key:** accepted higher risk of accidental or injected
  out-of-scope model calls. Rejected.
- **Per-request model validation in orchestrator:** adds code that can
  drift; LiteLLM enforcement is authoritative and cannot be bypassed by
  application bugs. Rejected as the primary control.