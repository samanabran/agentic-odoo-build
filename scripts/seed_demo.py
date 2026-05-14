#!/usr/bin/env python3
"""
Seed demo data into Odoo via JSON-RPC.

Creates:
  - Demo partners (for AML and reconciliation testing)
  - AML-triggering transactions (structuring pattern: 4 × ~$9200)
  - A bank statement with unreconciled lines
  - Matching posted account move lines (reconciliation candidates)

Usage:
    cd <project-root>
    python scripts/seed_demo.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass

import httpx

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB_NAME", "ai_brain_dev")
ODOO_PASS = os.getenv("ODOO_ADMIN_PASS", "admin")
TIMEOUT = 30.0
TODAY = date.today()


def rpc(session: httpx.Client, model: str, method: str, args: list, kwargs: dict | None = None) -> object:
    resp = session.post(
        f"{ODOO_URL}/web/dataset/call_kw",
        json={
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"model": model, "method": method, "args": args, "kwargs": kwargs or {}},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        msg = payload["error"].get("data", {}).get("message", str(payload["error"]))
        raise RuntimeError(f"Odoo RPC error ({model}.{method}): {msg}")
    return payload["result"]


def login(session: httpx.Client) -> int:
    resp = session.post(
        f"{ODOO_URL}/web/session/authenticate",
        json={"jsonrpc": "2.0", "method": "call", "id": 1,
              "params": {"db": ODOO_DB, "login": "admin", "password": ODOO_PASS}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    result = resp.json().get("result", {})
    uid = result.get("uid")
    if not uid:
        raise RuntimeError(f"Authentication failed: {resp.json()}")
    print(f"  Authenticated as admin (uid={uid})")
    return uid


def ensure_partner(session: httpx.Client, name: str, email: str) -> int:
    existing = rpc(session, "res.partner", "search", [[["name", "=", name]]], {"limit": 1})
    if existing:
        print(f"  Partner already exists: {name} (id={existing[0]})")
        return existing[0]
    pid = rpc(session, "res.partner", "create", [{"name": name, "email": email, "is_company": True}])
    print(f"  Created partner: {name} (id={pid})")
    return pid


def ensure_bank_statement_group(session: httpx.Client, uid: int) -> bool:
    """Grant whichever group allows account.bank.statement creation. Returns True if newly granted."""
    rules = rpc(session, "ir.model.access", "search_read",
                [[["model_id.model", "=", "account.bank.statement"], ["perm_create", "=", True]]],
                {"fields": ["group_id"], "limit": 1})
    if not rules or not rules[0].get("group_id"):
        print("  WARNING: no create-access rule found for account.bank.statement")
        return False
    group_id = rules[0]["group_id"][0]
    group_name = rules[0]["group_id"][1]
    user_groups = rpc(session, "res.users", "read", [[uid]], {"fields": ["groups_id"]})
    if user_groups and group_id in (user_groups[0].get("groups_id") or []):
        print(f"  Group '{group_name}' (id={group_id}) already granted to uid={uid}")
        return False
    rpc(session, "res.users", "write", [[uid], {"groups_id": [[4, group_id]]}])
    print(f"  Granted group '{group_name}' (id={group_id}) to uid={uid}")
    return True


def find_bank_journal(session: httpx.Client) -> dict:
    journals = rpc(
        session, "account.journal", "search_read",
        [[["type", "=", "bank"]]],
        {"fields": ["id", "name", "default_account_id"], "limit": 1},
    )
    if not journals:
        raise RuntimeError("No bank journal found — ensure Odoo accounting is configured")
    j = journals[0]
    print(f"  Using journal: {j['name']} (id={j['id']})")
    return j


def _resolve_account_id(raw) -> int | None:
    if isinstance(raw, (list, tuple)) and raw:
        return raw[0]
    if isinstance(raw, int):
        return raw
    return None


def find_counterpart_account(session: httpx.Client) -> int:
    for account_type in ["asset_receivable", "income", "income_other"]:
        accs = rpc(
            session, "account.account", "search_read",
            [[["deprecated", "=", False], ["account_type", "=", account_type]]],
            {"fields": ["id", "code", "name"], "limit": 1},
        )
        if accs:
            a = accs[0]
            print(f"  Counterpart account: {a['code']} {a['name']} (id={a['id']})")
            return a["id"]
    raise RuntimeError("Cannot find a suitable counterpart account")


def create_aml_moves(session: httpx.Client, partner_id: int, journal: dict, counterpart_id: int) -> list[int]:
    """4 transactions in 85%-99% of $10 000 threshold — triggers structuring detection."""
    amounts = [9200.0, 9400.0, 9100.0, 9300.0]
    bank_account_id = _resolve_account_id(journal.get("default_account_id"))
    if not bank_account_id:
        raise RuntimeError(f"Journal {journal['name']} has no default_account_id")

    created = []
    for i, amount in enumerate(amounts):
        move_date = TODAY - timedelta(days=i * 2)
        move_id = rpc(session, "account.move", "create", [{
            "journal_id": journal["id"],
            "date": str(move_date),
            "ref": f"SEED-AML-{partner_id}-{i + 1}",
            "line_ids": [
                [0, 0, {"account_id": bank_account_id, "partner_id": partner_id,
                        "name": f"AML seed txn {i + 1}", "debit": amount, "credit": 0.0}],
                [0, 0, {"account_id": counterpart_id, "partner_id": partner_id,
                        "name": f"AML seed txn {i + 1} offset", "debit": 0.0, "credit": amount}],
            ],
        }])
        rpc(session, "account.move", "action_post", [[move_id]])
        created.append(move_id)
        print(f"  AML move id={move_id}  amount={amount}  date={move_date}")
    return created


def create_bank_statement(session: httpx.Client, partner_id: int, journal: dict) -> int:
    """Bank statement with 2 lines for reconciliation testing."""
    stmt_id = rpc(session, "account.bank.statement", "create", [{
        "journal_id": journal["id"],
        "date": str(TODAY),
        "line_ids": [
            [0, 0, {"date": str(TODAY), "payment_ref": "SEED-STMT-1",
                    "amount": 1500.0, "partner_id": partner_id}],
            [0, 0, {"date": str(TODAY - timedelta(days=1)), "payment_ref": "SEED-STMT-2",
                    "amount": 2750.0, "partner_id": partner_id}],
        ],
    }])
    print(f"  Bank statement id={stmt_id} with 2 lines")
    return stmt_id


def create_reconciliation_moves(
    session: httpx.Client, partner_id: int, journal: dict, counterpart_id: int
) -> list[int]:
    """Posted moves matching the bank statement line amounts (1500 and 2750)."""
    amounts = [1500.0, 2750.0]
    bank_account_id = _resolve_account_id(journal.get("default_account_id"))
    if not bank_account_id:
        print("  WARNING: skipping reconciliation moves — no bank account on journal")
        return []

    created = []
    for i, amount in enumerate(amounts):
        move_date = TODAY - timedelta(days=i)
        move_id = rpc(session, "account.move", "create", [{
            "journal_id": journal["id"],
            "date": str(move_date),
            "ref": f"SEED-RECON-{i + 1}",
            "line_ids": [
                [0, 0, {"account_id": bank_account_id, "partner_id": partner_id,
                        "name": f"Recon seed {i + 1}", "debit": amount, "credit": 0.0}],
                [0, 0, {"account_id": counterpart_id, "partner_id": partner_id,
                        "name": f"Recon seed {i + 1} offset", "debit": 0.0, "credit": amount}],
            ],
        }])
        rpc(session, "account.move", "action_post", [[move_id]])
        created.append(move_id)
        print(f"  Reconciliation move id={move_id}  amount={amount}")
    return created


def main() -> None:
    print(f"\nSeeding demo data -> {ODOO_URL}  db={ODOO_DB}\n")

    with httpx.Client(follow_redirects=True) as session:
        uid = login(session)
        granted = ensure_bank_statement_group(session, uid)
        if granted:
            # Re-login so the new group takes effect (Odoo caches groups at session start)
            print("  Re-authenticating to pick up new group...")
            login(session)

        print("\n[1/4] Ensuring demo partners...")
        partner_a = ensure_partner(session, "Demo Corp A (Seed)", "demo-a@example.com")
        partner_b = ensure_partner(session, "Demo Corp B (Seed)", "demo-b@example.com")

        print("\n[2/4] Finding bank journal and accounts...")
        journal = find_bank_journal(session)
        counterpart_id = find_counterpart_account(session)

        print("\n[3/4] Creating AML test transactions (structuring pattern)...")
        create_aml_moves(session, partner_a, journal, counterpart_id)

        print("\n[4/4] Creating bank statement + reconciliation candidates...")
        create_bank_statement(session, partner_b, journal)
        create_reconciliation_moves(session, partner_b, journal, counterpart_id)

    print("\nSeed complete.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
