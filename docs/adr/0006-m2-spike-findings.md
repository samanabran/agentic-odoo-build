# ADR 0006 — M2 Spike: Apexive odoo-llm on Odoo 19 Compatibility

**Date:** 2026-05-06
**Status:** Accepted (static analysis complete; live install pending Docker)
**Branch:** m1-foundation (spike is read-only; no production code written)

---

## Method

Static analysis of the pinned submodule at SHA
`1ede75911bd4565a7f544be06e31a651f9d63cf7` (18.0 branch, 2026-05-01).
Live install test could not run because Docker Desktop was not running at
spike time. This ADR documents everything determinable from source reading
and flags what requires live validation. The live test must be run before
M2 scope is locked.

---

## Module inventory check

All 9 required modules from B1 Tier 2 are present in the submodule.

---

## Finding 1 — CERTAIN: Three hidden transitive dependencies (install list correction)

The B1 Tier 2 install list is **incomplete**. Three modules not in the list
are **required** by modules that are:

| Missing module | Required by | In vendor repo |
|---|---|---|
| `llm_store` | `llm_knowledge`, `llm_pgvector` | yes |
| `llm_training` | `llm_openai` | yes |
| `web_json_editor` | `llm_assistant` | yes |

**Corrected install order** (transitive deps resolved):

```
1.  llm
2.  llm_store          <- ADD
3.  llm_training       <- ADD
4.  web_json_editor    <- ADD
5.  llm_tool
6.  llm_thread
7.  llm_assistant
8.  llm_openai
9.  llm_ollama
10. llm_knowledge
11. llm_pgvector
12. llm_tool_knowledge
```

Without these three, Odoo will refuse to install `llm_openai`, `llm_knowledge`,
and `llm_pgvector` with a dependency error before any Odoo 19 compatibility
question arises.

---

## Finding 2 — CERTAIN: Custom Odoo Dockerfile required (Python packages)

The base `odoo:19.0` image does not include the following packages declared
via `external_dependencies.python`:

| Package | Required by |
|---|---|
| `emoji`, `markdown2` | llm_thread |
| `pydantic>=2.0.0`, `mcp` | llm_tool |
| `jinja2`, `jsonschema` | llm_assistant |
| `openai` | llm_openai |
| `ollama` | llm_ollama |
| `pgvector`, `numpy` | llm_pgvector |
| `markdownify`, `PyMuPDF`, `numpy` | llm_knowledge |

Odoo checks `external_dependencies.python` at install time and blocks
installation if a package is not importable.

**Resolution (M2 deliverable):** Add `infra/odoo/Dockerfile` extending
`odoo:19.0` with a single `RUN pip install ...` layer.

---

## Finding 3 — LOW RISK: t-esc deprecation (30+ instances, not a blocker)

`t-esc` appears in 30+ QWeb template locations across `llm_thread`,
`llm_generate`, and `llm_assistant`. Odoo 19 supports `t-esc` but deprecates
it in favour of `t-out`. Templates render correctly; no installation failure.
Deprecation warnings may appear in logs. Not a blocker; can be suppressed
with `ai_brain` template overrides if needed.

---

## Finding 4 — MODERATE RISK: llm_thread patches Odoo 19 mail OWL components

`llm_thread` patches five core mail components via `patch()`:

| File | Target |
|---|---|
| `composer_patch.js` | `Composer.prototype` from `@mail/core/common/composer` |
| `thread_patch.js` | `Thread.prototype` from `@mail/core/common/thread_model` |
| `thread_model_patch.js` | `Thread.prototype` (URL routing extension) |
| `chatter_patch.js` | chatter component |
| `message_patch.js` | message component |

The `patch()` API is stable (OWL 2). The `Composer` patch wraps its
`useService("llm.store")` in `try/catch` for graceful degradation.

**Risk:** If Odoo 19 changed method signatures inside `Thread.prototype` or
`Composer.prototype.setup()`, patches could silently mis-apply or throw at
runtime. Cannot be determined from source reading alone.

**Assessment:** This is the primary unknown requiring live validation.

---

## Finding 5 — CLEAN: llm_pgvector pre_init_hook

The hook calls `CREATE EXTENSION IF NOT EXISTS vector` and verifies the
type with a test query. Our `pgvector/pgvector:pg16` image has pgvector
pre-installed. The hook's `IF NOT EXISTS` guard means it will log "already
installed" and continue cleanly.

---

## Finding 6 — CLEAN: No deprecated ORM patterns

- `@api.multi` — not found
- OWL 1 legacy patterns (`patchMap`, `Component.env`, `LegacyComponent`) — not found
- The 18->19 ORM delta is incremental, not structural

---

## Live install validation (pending Docker Desktop start)

Command to run once Docker is available:

```bash
make up
# inside Odoo container after startup:
pip install emoji markdown2 "pydantic>=2.0.0" mcp jinja2 jsonschema \
    openai ollama pgvector numpy markdownify PyMuPDF
odoo -c /etc/odoo/odoo.conf \
    -i llm,llm_store,llm_training,web_json_editor,llm_tool,llm_thread,\
llm_assistant,llm_openai,llm_ollama,llm_knowledge,llm_pgvector,llm_tool_knowledge \
    --stop-after-init 2>&1 | tee /tmp/m2_spike.log
```

Update this ADR with the per-module results (installs cleanly / warnings /
failure + stack trace) before M2 scope is committed.

---

## Preliminary recommendation

**Yellow path — pending live confirmation.**

Two issues are certain and have clear, bounded resolutions:
- Install list corrected (+3 transitive modules: `llm_store`, `llm_training`, `web_json_editor`)
- Custom Odoo Dockerfile required (pip layer, M2 deliverable)

One issue is a moderate unknown that live testing will resolve:
- `llm_thread` frontend patches against Odoo 19 mail OWL components

If live validation shows frontend patches apply cleanly: upgrade to **Green**
path, M2 proceeds as planned (~1 week).

If patches require `ai_brain` OWL overrides: stays **Yellow**, M2 grows to
~2 weeks.

Static analysis gives no signal for a Red path. Modules `llm`, `llm_thread`,
and `llm_assistant` have clean ORM with no Odoo 19 structural incompatibilities
visible from source. The 18->19 delta is incremental as expected per ADR 0004.

---

## Decision

**Pending live validation.** Update the recommendation above once the live
install test is run.

| Scenario | Path | M2 estimate |
|---|---|---|
| All 12 install + patches apply cleanly | Green | ~1 week |
| 1-3 frontend patch failures, fixable in ai_brain | Yellow | ~2 weeks |
| llm / llm_thread / llm_assistant fail at ORM level | Red | revisit ADR 0004 |
