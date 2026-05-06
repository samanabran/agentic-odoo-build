# ADR 0004 — Odoo Version Decision

**Date:** 2026-05-06
**Status:** Accepted

## Compatibility report (Section C1)

### (a) Branches on apexive/odoo-llm

Active branches as of 2026-05-06: `16.0`, `18.0` (default, last commit 2026-05-01).
No `19.0` branch exists. Maintainers announced a port "after Christmas 2025";
as of this date (5+ months later) no branch has appeared.

### (b) Which target Odoo 19 / 18?

- Odoo 19: none.
- Odoo 18: `18.0` branch (all modules, actively maintained).

### (c) Per-module port status

All 11 required modules (`llm`, `llm_thread`, `llm_tool`, `llm_assistant`,
`llm_openai`, `llm_ollama`, `llm_pgvector`, `llm_knowledge`,
`llm_tool_knowledge`, `llm_mcp_server`, `llm_tool_account`) are present and
maintained on the `18.0` branch. None have a `19.0` port.

### (d) Estimated porting effort

Under the B2 constraint (vendor diff must remain zero, no patching in place),
compatibility issues are resolved via `ai_brain` Odoo inheritance overrides.
Known 18→19 changes: manifest version strings (not an install blocker),
`t-esc` → `t-out` in QWeb (overridable via template inheritance),
ORM namespace cleanup (resolvable in `ai_brain`).

Estimated effort in M2: **2–5 days** if modules load cleanly; up to 8 days if
anything requires a fork (which triggers ADR 0002b).

### (e) Options considered

| Option | Description | Risk |
|---|---|---|
| A | Odoo 19 + accept porting effort | Unknown breakage scope until runtime |
| B | Odoo 18 for v1, upgrade later | Zero M2 porting risk; adds future upgrade project |
| C | Odoo 19 + subset that works + build rest ourselves | Same as A with more custom code |

## Decision

**Option A — Odoo 19 Community Edition.**

Chosen by the project owner on 2026-05-06.

Rationale: Odoo 19 is the current stable release; `productivity.ai` (one of
our two required foundations) is at its most capable version; no future
upgrade project to manage.

Risk acceptance: If vendor module loading on Odoo 19 requires a fork, ADR 0002b
will be opened and the porting scope bounded before M2 merges.
