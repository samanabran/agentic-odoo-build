# ADR 0002 — Apexive odoo-llm Vendor Pinning

**Date:** 2026-05-06
**Status:** Accepted

## Context

We use `apexive/odoo-llm` as a git submodule (added in M2). The pinned
SHA must be recorded here and updated via a "vendor bump" PR whenever
we advance the pin (B3). CI must run the full eval harness against any
vendor bump before it can merge.

## Pinned commit

| Field | Value |
|---|---|
| Repository | https://github.com/apexive/odoo-llm |
| Branch | 18.0 |
| SHA | `1ede75911bd4565a7f544be06e31a651f9d63cf7` |
| Date | 2026-05-01 |
| Commit message | "Merge pull request #240 from moctarjallo/feat/llm-generate-attachments" |

## Vendor diff policy (B2)

The diff between `addons/vendor/odoo-llm` and the upstream pinned commit
MUST be zero at all times. Verified by:

```bash
git -C addons/vendor/odoo-llm diff --quiet HEAD
```

If a change is needed in vendor code:
1. Override from `addons/ai_brain` using Odoo inheritance.
2. Open a PR to `apexive/odoo-llm` upstream.
3. Fork to `addons/vendor/odoo-llm-fork` as a last resort (requires its own ADR).

Never patch vendor files in place.

## Odoo 19 compatibility

We are running Odoo 19 Community with 18.0-branch vendor modules. The
18→19 migration delta is incremental (manifest version strings, t-esc→t-out,
ORM namespace cleanup). Odoo 19 does not refuse to install modules whose
manifest version says 18.0.x.y.z.

Any compatibility issues discovered in M2 will be resolved via `ai_brain`
overrides. If a fork proves necessary, ADR 0002b will be opened.

## Bump procedure

1. Run `git -C addons/vendor/odoo-llm fetch origin 18.0 && git -C addons/vendor/odoo-llm checkout <new-sha>`.
2. Update this file with the new SHA and rationale.
3. Open a dedicated "vendor bump" PR (separate from feature work).
4. CI must run `make eval` and pass before the PR can merge.
