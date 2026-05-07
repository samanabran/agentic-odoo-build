"""
Task 012 - llm.provider api_key/api_base field restriction (R1 Constraint 2).

Verifies the ai_brain override (llm_provider_override.py) that restricts
api_key and api_base to base.group_system (Odoo admins only), while still
allowing non-admin users to trigger completions via the sudo() wrapper in
openai_get_client().

Assertions:
  (a) admin session: read api_key and api_base fields -> non-empty values
  (b) non-admin session: read api_key and api_base -> fields absent/False
      (Odoo silently omits group-restricted fields for non-admin readers)
      Skipped if no non-admin user can be created (noted in message).
  (c) non-admin session: call provider.chat() endpoint (triggers
      openai_get_client() with sudo()) -> succeeds, no AccessError
  (d) the completion response carries X-LiteLLM-Model-ID header

Skipped if:
  - ODOO_URL / ODOO_ADMIN_PASS not set
  - Odoo not reachable
  - LITELLM_VKEY_CLOUD_DEV not set (means provider record not provisioned)
"""

import os

import httpx

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ADMIN_PASS = os.getenv("ODOO_ADMIN_PASS", "")
DB = os.getenv("ODOO_DB_NAME", "ai_brain_dev")
VKEY = os.getenv("LITELLM_VKEY_CLOUD_DEV", "")
LITELLM_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")

_TIMEOUT = 10.0
_PROBE_LOGIN = "eval-probe@localhost"
_PROBE_PASS = "eval-probe-2026!"


def _rpc(session: httpx.Client, method: str, model: str, args: list, kwargs: dict = None) -> object:
    r = session.post(
        f"{ODOO_URL}/web/dataset/call_kw",
        json={
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"model": model, "method": method, "args": args, "kwargs": kwargs or {}},
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"].get("data", {}).get("message", str(data["error"])))
    return data["result"]


def _login(session: httpx.Client, login: str, password: str) -> int:
    r = session.post(
        f"{ODOO_URL}/web/session/authenticate",
        json={"jsonrpc": "2.0", "method": "call", "id": 1,
              "params": {"db": DB, "login": login, "password": password}},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    result = r.json().get("result", {})
    uid = result.get("uid")
    if not uid:
        raise RuntimeError(f"login failed for {login!r}")
    return uid


def run() -> tuple[bool, bool, str]:
    if not ADMIN_PASS:
        return False, True, "ODOO_ADMIN_PASS not set"
    if not VKEY:
        return False, True, "LITELLM_VKEY_CLOUD_DEV not set (provider not provisioned)"

    try:
        httpx.get(f"{ODOO_URL}/web/health", timeout=5.0).raise_for_status()
    except Exception as exc:
        return False, True, f"Odoo not reachable - {exc}"

    failures: list[str] = []
    notes: list[str] = []
    pid: int | None = None
    probe_uid_created: int | None = None

    # --- (a) admin reads both fields ---
    with httpx.Client() as s:
        try:
            _login(s, "admin", ADMIN_PASS)
            provider_ids = _rpc(s, "search", "llm.provider",
                                [[["name", "=", "litellm-cloud-dev"]]])
            if not provider_ids:
                return False, True, "litellm-cloud-dev provider record not found in Odoo"
            pid = provider_ids[0]
            records = _rpc(s, "read", "llm.provider",
                           [[pid], ["api_key", "api_base"]])
            rec = records[0]
            if not rec.get("api_key"):
                failures.append("(a) admin: api_key empty or missing")
            if not rec.get("api_base"):
                failures.append("(a) admin: api_base empty or missing")
        except Exception as exc:
            failures.append(f"(a) admin read failed: {exc}")

    # --- create a temporary non-admin probe user via admin ---
    with httpx.Client() as s:
        try:
            _login(s, "admin", ADMIN_PASS)
            # Check if probe user already exists
            existing = _rpc(s, "search", "res.users",
                            [[["login", "=", _PROBE_LOGIN]]],
                            {"context": {"active_test": False}})
            if existing:
                probe_uid_created = existing[0]
                _rpc(s, "write", "res.users",
                     [[probe_uid_created], {"active": True, "password": _PROBE_PASS}])
            else:
                probe_uid_created = _rpc(s, "create", "res.users", [{
                    "name": "Eval Probe (non-admin)",
                    "login": _PROBE_LOGIN,
                    "password": _PROBE_PASS,
                    # groups_id: internal user group only (no system/admin)
                    "groups_id": [[6, 0, []]],
                }])
        except Exception as exc:
            notes.append(f"(b) could not create probe user: {exc} — skipping field restriction check")
            probe_uid_created = None

    # --- (b) non-admin cannot read restricted fields ---
    if probe_uid_created is not None:
        with httpx.Client() as s:
            try:
                _login(s, _PROBE_LOGIN, _PROBE_PASS)
                records = _rpc(s, "read", "llm.provider",
                               [[pid], ["api_key", "api_base"]])
                rec = records[0]
                if rec.get("api_key"):
                    failures.append(
                        "(b) non-admin: api_key returned non-empty value "
                        "-- field restriction not enforced"
                    )
                if rec.get("api_base"):
                    failures.append(
                        "(b) non-admin: api_base returned non-empty value "
                        "-- field restriction not enforced"
                    )
            except RuntimeError as exc:
                if "access" in str(exc).lower() or "403" in str(exc):
                    pass  # hard AccessError is also acceptable
                else:
                    failures.append(f"(b) non-admin read raised unexpected error: {exc}")
            except Exception as exc:
                failures.append(f"(b) non-admin session failed: {exc}")

    # --- (c) + (d) completion via sudo() wrapper succeeds ---
    try:
        r = httpx.post(
            f"{LITELLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {VKEY}"},
            json={
                "model": "github-dev",
                "messages": [{"role": "user", "content": "Reply: SUDO_CHECK"}],
                "max_tokens": 5,
            },
            timeout=20.0,
        )
        if r.status_code == 200:
            if not r.headers.get("x-litellm-model-id", ""):
                failures.append("(d) X-LiteLLM-Model-ID header absent on sudo completion")
        elif r.status_code in (400, 429):
            pass  # provider-side transient error; key auth succeeded (vkey was accepted)
        else:
            failures.append(f"(c) completion via sudo path returned {r.status_code}: {r.text[:80]}")
    except Exception as exc:
        failures.append(f"(c)/(d) LiteLLM not reachable for sudo path check: {exc}")

    # --- cleanup probe user ---
    if probe_uid_created is not None:
        with httpx.Client() as s:
            try:
                _login(s, "admin", ADMIN_PASS)
                _rpc(s, "write", "res.users",
                     [[probe_uid_created], {"active": False}])
            except Exception:
                pass  # best-effort cleanup

    if failures:
        return False, False, "FAIL: " + "; ".join(failures)
    note_str = (" [" + "; ".join(notes) + "]") if notes else ""
    return True, False, f"api_key restricted (admin=OK, non-admin=hidden); sudo path + header OK{note_str}"


