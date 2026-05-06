# ADR 0010 - LLM Provider api_key Field Restriction (Constraint 2 of R1)

**Date:** 2026-05-07
**Status:** Accepted

## Context

Apexive's `llm.provider` model declares:

```python
api_key = fields.Char()
api_base = fields.Char()
```

Both fields are plain `Char` with no access restriction. Any internal Odoo
user with `read` access on `llm.provider` (default for all internal users)
can retrieve the raw LiteLLM virtual key and the internal service URL via
XML-RPC `model.read()` or the form view.

`openai_get_client()` reads `self.api_key` directly. If the field were
restricted without a `sudo()` wrapper, non-admin completions would silently
pass `api_key=False` to the OpenAI client, causing a 401 from LiteLLM.

## Decision

Override both fields in `addons/ai_brain/models/llm_provider_override.py`
with `groups="base.group_system"` and add a `sudo()` read path in
`openai_get_client()`:

```python
class LLMProvider(models.Model):
    _inherit = "llm.provider"

    api_key = fields.Char(groups="base.group_system")
    api_base = fields.Char(groups="base.group_system")

    def openai_get_client(self):
        record = self.sudo()
        return OpenAI(api_key=record.api_key, base_url=record.api_base or None)
```

**Effect of `groups="base.group_system"`:**

- Odoo's ORM silently returns `False` for this field when read by a
  non-admin user. It does not raise `AccessError` on `read()` — it omits.
- The field is invisible in all views for non-admin users.
- XML-RPC `fields_get()` does not expose the field to non-admin callers.

**Effect of `self.sudo()`:**

- `sudo()` creates a new recordset with `uid=SUPERUSER_ID` scoped to this
  call only. It does not elevate the user's session globally.
- The `api_key` value is only read at the point of client construction,
  not stored in memory beyond the request.

## Consequences

- Non-admin users can trigger LLM completions (the sudo wrapper handles
  key access transparently) but cannot exfiltrate the key via the UI or API.
- The Odoo audit log (`ai.tool.log`) records the acting `user_id` (the real
  user), not the superuser — the sudo call does not obscure attribution.
- **Future:** when Odoo ships native encrypted `Char` field support, this
  override should be updated to use that mechanism for at-rest protection.
  The `groups` restriction covers in-transit and UI exposure only.

## Verification

`task_012_llm_openai_non_admin_read` asserts all four properties:

| Assert | Check |
|---|---|
| (a) | admin reads non-empty `api_key` and `api_base` |
| (b) | non-admin reads return `False`/absent for both fields |
| (c) | non-admin LiteLLM call (via `sudo()` wrapper) returns 200 |
| (d) | response carries `X-LiteLLM-Model-ID` header |

## Alternatives rejected

- **`password=True` on `Char`:** masks in UI but does not restrict ORM reads.
  Non-admin XML-RPC `read()` still returns the plaintext value. Rejected.
- **`res.config.settings` storage:** would require a separate settings model
  and `get_param` / `set_param` indirection. Adds complexity with no
  additional access control beyond `groups=`. Rejected for M2 scope.
- **No restriction (vendor default):** any internal user could exfiltrate the
  virtual key and use it to exhaust the daily GitHub Models quota or probe
  LiteLLM internals. Rejected.

## Live verification (PR #7 — 2026-05-07)

llm.provider records confirmed in i_brain_dev DB after i_brain module install:

`sql
SELECT id, name, api_base FROM llm_provider ORDER BY id;
 id |       name        |        api_base
----+-------------------+------------------------
  1 | litellm-cloud-dev | http://litellm:4000/v1
  2 | litellm-local     | http://litellm:4000/v1
`

pi_key field updated with scoped LiteLLM virtual keys via scripts/provision_litellm_keys.sh.
ORM write used authenticated admin session (JSON-RPC, cookie-based auth).
Status: **observed**.
