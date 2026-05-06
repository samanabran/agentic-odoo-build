# ADR 0006 — M2 Spike: Apexive odoo-llm on Odoo 19 Compatibility

**Date:** 2026-05-06
**Status:** Accepted — FINAL (live install test complete)
**Branch:** m1-foundation (spike read-only; no production code written)

---

## Method

Static analysis of the pinned submodule at SHA
`1ede75911bd4565a7f544be06e31a651f9d63cf7` (18.0 branch, 2026-05-01),
followed by a live install test on a fresh `odoo:19.0` container with
Python packages pre-installed.

---

## Live install test — command run

```bash
docker exec infra-odoo-1 odoo \
  --addons-path="/mnt/extra-addons,/mnt/extra-addons/vendor/odoo-llm" \
  -d spike_test --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -i llm,llm_store,llm_training,web_json_editor,llm_tool,llm_thread,\
llm_assistant,llm_openai,llm_ollama,llm_knowledge,llm_pgvector,llm_tool_knowledge \
  --stop-after-init --no-http
```

---

## Finding 1 — BLOCKER: Odoo 19 version check rejects ALL 18.0 modules

**Status per module (live test):**

| Module | Result | Odoo 19 log |
|---|---|---|
| llm | BLOCKED | incompatible version, setting installable=False |
| llm_store | BLOCKED | incompatible version, setting installable=False |
| llm_training | BLOCKED | incompatible version, setting installable=False |
| web_json_editor | BLOCKED | incompatible version, setting installable=False |
| llm_tool | BLOCKED | incompatible version, setting installable=False |
| llm_thread | BLOCKED | incompatible version, setting installable=False |
| llm_assistant | BLOCKED | incompatible version, setting installable=False |
| llm_openai | BLOCKED | incompatible version, setting installable=False |
| llm_ollama | BLOCKED | incompatible version, setting installable=False |
| llm_knowledge | BLOCKED | incompatible version, setting installable=False |
| llm_pgvector | BLOCKED | incompatible version, setting installable=False |
| llm_tool_knowledge | BLOCKED | incompatible version, setting installable=False |

**Root cause — `check_version()` in `odoo/modules/module.py`:**

```python
def check_version(version, should_raise=True):
    version = adapt_version(version)
    serie = release.major_version  # "19.0" on Odoo 19
    if version.startswith(serie + '.'):
        return True
    return False

# Called at manifest load time:
if manifest['installable'] and not check_version(manifest['version'], should_raise=False):
    manifest['installable'] = False  # HARD BLOCK — no override path
```

All vendor modules carry version strings of the form `18.0.x.y.z`.
Odoo 19 requires `19.0.x.y.z`. The check runs before any add-on code
executes, so there is no monkey-patch path via `ai_brain/__init__.py`.
There is no CLI flag to bypass this check. There is no inheritance
mechanism to override a module's manifest version.

**The B2 zero-diff constraint prevents us from changing vendor manifests
in place. This is a structural hard block, not a compatibility warning.**

---

## Finding 2 — CERTAIN (static, unblocked by live test)

Three transitive deps must be added to the install list regardless of
which Odoo version is used:
- `llm_store` (required by llm_knowledge, llm_pgvector)
- `llm_training` (required by llm_openai)
- `web_json_editor` (required by llm_assistant)

All three are in the vendor repo.

---

## Finding 3 — Odoo Python setup note

The `odoo:19.0` base image uses system-managed Python (PEP 668).
Installing packages requires `pip install --break-system-packages`.
This must be handled by a custom Dockerfile in M2 regardless of which
Odoo version is chosen.

---

## Decision — RED PATH

All 9 required modules (including the three critical ones: `llm`,
`llm_thread`, `llm_assistant`) fail to install on Odoo 19 due to the
version string enforcement introduced in Odoo 19.

**Recommended action per ADR 0005 rollback plan:**

> If a hard blocker is discovered... the fallback is:
> 1. Change `odoo` image from `odoo:19.0` to `odoo:18.0`.
> 2. Update `addons/ai_brain/__manifest__.py` version prefix from
>    `19.0` to `18.0`.
> 3. Update this ADR to reflect the downgrade.
> 4. Notify the project owner; document the blocking issue.

**The rollback is a one-commit change.** It does not affect the
orchestrator, LiteLLM, Redis, or any infrastructure outside the Odoo
container.

**Alternative (do NOT pursue without explicit owner decision):**
Fork all 9 vendor modules, bump version strings to `19.0.x.y.z`, and
open upstream PRs. This scopes a real M2.5 porting milestone (~3–4
weeks), requires ADR 0002b, and carries unknown frontend patch risk.

---

## Recommendation to project owner

Downgrade to Odoo 18 Community (one commit) and proceed with M2 as
planned. The vendor modules are actively maintained on the 18.0 branch.
Odoo 18 is supported until October 2027. The upgrade to Odoo 19 can be
revisited once Apexive publishes an official 19.0 branch (which they
announced but have not shipped 5+ months later).
