"""
E2E tests for Odoo AI Brain — covers Odoo UI flows and API endpoints.

Run with:
    cd orchestrator && python -m pytest tests/test_e2e.py -v --headed
    or headless:
    cd orchestrator && python -m pytest tests/test_e2e.py -v
"""

import os
import time

import httpx
import jwt as pyjwt
import pytest
from dotenv import load_dotenv

load_dotenv(str(__file__).replace("orchestrator/tests/test_e2e.py", ".env").replace(
    "orchestrator\\tests\\test_e2e.py", ".env"
))

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ORCH_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8088")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
ODOO_DB = os.getenv("ODOO_DB_NAME", "ai_brain_dev")
ODOO_PASS = os.getenv("ODOO_ADMIN_PASS", "admin")
JWT_SECRET = os.getenv("ORCH_JWT_SECRET", "")
LITELLM_KEY = os.getenv("LITELLM_MASTER_KEY", "")


def _mint_jwt(user_id: int = 1) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + 300},
        JWT_SECRET,
        algorithm="HS256",
    )


# ── API tests (no browser) ────────────────────────────────────────────────────

class TestOrchestratorAPI:
    def test_health(self):
        r = httpx.get(f"{ORCH_URL}/health", timeout=5)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_narrative_aml(self):
        if not JWT_SECRET:
            pytest.skip("ORCH_JWT_SECRET not set")
        r = httpx.post(
            f"{ORCH_URL}/tools/narrative",
            json={
                "task": "aml_narrative",
                "items": [
                    {"partner_id": 7, "alert_type": "structuring",
                     "transaction_count": 4, "total_amount": 39200.0},
                ],
            },
            headers={"Authorization": f"Bearer {_mint_jwt()}"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "narrative" in data
        assert len(data["narrative"].strip()) > 50, "Narrative too short"

    def test_narrative_reconciliation(self):
        if not JWT_SECRET:
            pytest.skip("ORCH_JWT_SECRET not set")
        r = httpx.post(
            f"{ORCH_URL}/tools/narrative",
            json={
                "task": "reconciliation_rationale",
                "items": [
                    {"amount": 1500.0, "partner": "Vendor A", "date": "2026-05-01"},
                ],
            },
            headers={"Authorization": f"Bearer {_mint_jwt()}"},
            timeout=30,
        )
        assert r.status_code == 200
        assert len(r.json()["narrative"].strip()) > 50

    def test_narrative_rejects_invalid_jwt(self):
        r = httpx.post(
            f"{ORCH_URL}/tools/narrative",
            json={"task": "aml_narrative", "items": []},
            headers={"Authorization": "Bearer invalid.token.here"},
            timeout=5,
        )
        assert r.status_code == 401

    def test_chat_endpoint(self):
        if not JWT_SECRET:
            pytest.skip("ORCH_JWT_SECRET not set")
        r = httpx.post(
            f"{ORCH_URL}/chat",
            json={"prompt": "Say PONG and nothing else.", "thread_id": 1},
            headers={"Authorization": f"Bearer {_mint_jwt()}"},
            timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "reply" in data, f"Missing reply key: {data}"
        assert len(data["reply"].strip()) > 0, "Empty reply"
        assert "user_id" in data

    def test_narrative_rejects_unknown_task(self):
        if not JWT_SECRET:
            pytest.skip("ORCH_JWT_SECRET not set")
        r = httpx.post(
            f"{ORCH_URL}/tools/narrative",
            json={"task": "nonexistent_task", "items": []},
            headers={"Authorization": f"Bearer {_mint_jwt()}"},
            timeout=5,
        )
        assert r.status_code == 422


class TestLiteLLMProxy:
    def test_liveness(self):
        r = httpx.get(f"{LITELLM_URL}/health/liveliness", timeout=5)
        assert r.status_code == 200
        assert "alive" in r.text.lower()

    def test_models_list(self):
        if not LITELLM_KEY:
            pytest.skip("LITELLM_MASTER_KEY not set")
        r = httpx.get(
            f"{LITELLM_URL}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=5,
        )
        assert r.status_code == 200
        models = [m["id"] for m in r.json()["data"]]
        for required in ["github-dev", "prod-default", "prod-local", "prod-alternate"]:
            assert required in models, f"Missing model: {required}"


class TestOdooAPI:
    def _authenticate(self) -> dict:
        r = httpx.post(
            f"{ODOO_URL}/web/session/authenticate",
            json={"jsonrpc": "2.0", "method": "call", "id": 1,
                  "params": {"db": ODOO_DB, "login": "admin", "password": ODOO_PASS}},
            timeout=15,
        )
        r.raise_for_status()
        result = r.json().get("result", {})
        assert result.get("uid"), f"Auth failed: {r.json()}"
        return {"Cookie": f"session_id={r.cookies.get('session_id', '')}"}

    def test_odoo_login(self):
        headers = self._authenticate()
        assert headers

    def test_finance_dashboard_accessible(self):
        headers = self._authenticate()
        r = httpx.get(f"{ODOO_URL}/ai_brain/dashboard", headers=headers, timeout=10)
        assert r.status_code == 200
        assert any(kw in r.text for kw in ["Financial Intelligence", "AI Brain", "dashboard"])

    def test_aml_check_via_rpc(self):
        headers = self._authenticate()
        r = httpx.post(
            f"{ODOO_URL}/web/dataset/call_kw",
            json={"jsonrpc": "2.0", "method": "call", "id": 1,
                  "params": {"model": "ai.brain.finance", "method": "check_aml_patterns",
                             "args": [[], [1, 2, 3], 30, 10000.0], "kwargs": {}}},
            headers=headers,
            timeout=20,
        )
        assert r.status_code == 200
        result = r.json().get("result")
        assert isinstance(result, dict), f"Unexpected result: {r.json()}"
        assert "partners_flagged" in result
        assert "alerts_created" in result

    def test_reconciliation_suggest_via_rpc(self):
        headers = self._authenticate()
        # Find a real bank statement ID first
        r = httpx.post(
            f"{ODOO_URL}/web/dataset/call_kw",
            json={"jsonrpc": "2.0", "method": "call", "id": 1,
                  "params": {"model": "account.bank.statement",
                             "method": "search",
                             "args": [[]], "kwargs": {"limit": 1}}},
            headers=headers,
            timeout=15,
        )
        stmt_ids = r.json().get("result", [])
        if not stmt_ids:
            pytest.skip("No bank statements in DB")
        r = httpx.post(
            f"{ODOO_URL}/web/dataset/call_kw",
            json={"jsonrpc": "2.0", "method": "call", "id": 1,
                  "params": {"model": "ai.brain.finance",
                             "method": "suggest_bank_reconciliation",
                             "args": [[], stmt_ids[0]], "kwargs": {}}},
            headers=headers,
            timeout=20,
        )
        assert r.status_code == 200
        result = r.json().get("result")
        assert isinstance(result, dict), f"Unexpected result: {r.json()}"
        assert "session_id" in result or "state" in result


# ── Browser tests (Playwright) ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser_page(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
    browser.close()


class TestOdooBrowser:
    def test_login_page_loads(self, browser_page):
        browser_page.goto(f"{ODOO_URL}/web/login")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        assert "Odoo" in browser_page.title() or browser_page.query_selector("input[name='login']")

    def test_admin_login(self, browser_page):
        browser_page.goto(f"{ODOO_URL}/web/login")
        browser_page.wait_for_load_state("domcontentloaded", timeout=15000)
        login_field = browser_page.query_selector("input[name='login']")
        if not login_field:
            pytest.skip("Login page not accessible")
        login_field.fill("admin")
        browser_page.fill("input[name='password']", ODOO_PASS)
        browser_page.click("button[type='submit']")
        browser_page.wait_for_url("**/odoo/**", timeout=20000)
        assert "/odoo/" in browser_page.url or "/web" in browser_page.url, \
            f"Expected /odoo/ or /web after login, got: {browser_page.url}"

    def test_finance_dashboard_browser(self, browser_page):
        browser_page.goto(f"{ODOO_URL}/ai_brain/dashboard")
        browser_page.wait_for_load_state("networkidle", timeout=15000)
        content = browser_page.content()
        assert any(kw in content for kw in [
            "Financial Intelligence", "AI Brain", "dashboard", "reconciliation"
        ])
