# ADR 0003 — GitHub Models: Development and Evaluation Use Only

**Date:** 2026-05-06
**Status:** Accepted

## Context

The team holds an active GitHub Copilot subscription (Pro or higher). This subscription includes
an elevated GitHub Models API rate-limit allowance beyond the free tier. The addendum requires us
to (a) record the actual rate limits, (b) route development and evaluation traffic through GitHub
Models, and (c) hard-block GitHub Models endpoints in production.

## Rate limits recorded from catalog

Queried `GET https://models.github.ai/catalog/models` on 2026-05-06 (unauthenticated; the catalog
endpoint is public). The response lists 43 models across two rate-limit tiers. Per-model quotas
are documented in GitHub's official docs at:
https://docs.github.com/en/github-models/prototyping-with-ai-models

| Tier | Model examples | Req / min | Req / day (Copilot) | Tokens / request |
|---|---|---|---|---|
| **low** | gpt-4o-mini, phi-4, mistral-small, llama-3.1-8b | 15 | 150–300 | 8 K in / 4 K out |
| **high** | gpt-4o, llama-3.3-70b, llama-4-maverick | 10 | 50–100 | 8 K in / 4 K out |
| **embeddings** | text-embedding-3-small/large | separate limits | — | — |

> **Action required:** To verify the limits for the team's specific token, run:
> ```bash
> curl -I -H "Authorization: Bearer $GITHUB_TOKEN" \
>   https://models.inference.ai.azure.com/chat/completions \
>   -H "Content-Type: application/json" \
>   -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}],"max_tokens":1}'
> # Check response headers: x-ratelimit-limit-requests, x-ratelimit-remaining-requests, etc.
> ```

**Selected dev model:** `openai/gpt-4o-mini` via GitHub Models (`low` tier, 150–300 req/day on
Copilot). This matches the production default model, keeping eval results comparable.

## Decision

1. **Permitted:** GitHub Models (`github-dev` route in LiteLLM) for local development, the `make eval`
   harness, and team-internal demos. Configure via `GITHUB_TOKEN` in `.env`.

2. **Forbidden in production:** The orchestrator refuses to start if `ENVIRONMENT=production` and
   `DEFAULT_MODEL` references a GitHub endpoint. This is a hard error, not a warning, to prevent
   accidental production misconfiguration.

3. **Copilot IDE tooling is unrelated:** Copilot assists developers while writing code. It is not
   called at runtime by the Odoo AI Brain system. The two uses share the same subscription but are
   completely separate code paths.

4. **No reverse-engineered Copilot proxies:** We do not document or implement tools that expose
   Copilot's internal endpoints as OpenAI-compatible APIs.

## Routing summary

| `ENVIRONMENT` | Default route | GitHub Models allowed? |
|---|---|---|
| `development` | `github-dev` (GitHub Models `gpt-4o-mini`) | Yes |
| `production` | `gpt-4o-mini` (OpenAI) or `claude-haiku` (Anthropic) | **No — hard error** |
| `production` + `PRIVATE_MODE=true` | `local` (Ollama `qwen2.5:7b`) | **No — hard error** |

## Consequences

- `GITHUB_TOKEN` is a required variable in `.env` for development. It must never be committed.
- Evaluation results run against `gpt-4o-mini` via GitHub Models; production uses the same model
  via OpenAI. Minor behavioural differences are expected and should be noted in evaluation reports.
- Rate limits (150–300 req/day) are sufficient for the `make eval` golden-task set (≤ 30 tasks in
  M8) but will be exhausted quickly if the harness is run many times per day. Use `--filter` flags
  to run subsets during iteration.
