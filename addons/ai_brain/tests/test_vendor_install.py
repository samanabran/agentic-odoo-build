# -*- coding: utf-8 -*-
"""
Tests: vendor module installation and seed assistant data (M2).

These tests run inside an Odoo environment (e.g. via `make test` which invokes
pytest inside the Odoo container).  They use the Odoo ORM — no HTTP calls.

If running outside an Odoo container these tests are automatically skipped.
"""
import pytest

# Skip the whole module if Odoo ORM is not available
odoo = pytest.importorskip("odoo")

try:
    from odoo.tests.common import TransactionCase
except Exception:
    TransactionCase = None

EXPECTED_INSTALLED = [
    "llm",
    "llm_thread",
    "llm_tool",
    "llm_assistant",
    "llm_openai",
    "llm_ollama",
    "llm_pgvector",
    "llm_knowledge",
    "llm_tool_knowledge",
]

EXPECTED_NOT_INSTALLED = [
    "llm_mcp_server",
    "llm_tool_account",
]


@pytest.mark.skipif(TransactionCase is None, reason="Odoo ORM not available")
class TestVendorInstall(TransactionCase):
    def test_expected_modules_installed(self):
        """All 9 required vendor modules must be in state 'installed'."""
        env = self.env
        for name in EXPECTED_INSTALLED:
            module = env["ir.module.module"].search(
                [("name", "=", name), ("state", "=", "installed")]
            )
            assert module, f"Module '{name}' is not installed"

    def test_deferred_modules_not_installed(self):
        """llm_mcp_server and llm_tool_account must NOT be installed yet (M7)."""
        env = self.env
        for name in EXPECTED_NOT_INSTALLED:
            module = env["ir.module.module"].search(
                [("name", "=", name), ("state", "=", "installed")]
            )
            assert not module, (
                f"Module '{name}' should not be installed until M7 but found state=installed"
            )

    def test_dev_assistant_exists(self):
        """Dev Assistant must exist and be linked to the cloud-dev provider."""
        assistant = self.env["llm.assistant"].search(
            [("name", "=", "Dev Assistant")]
        )
        assert assistant, "Dev Assistant not found — check llm_providers.xml"
        provider = assistant.provider_id
        assert provider, "Dev Assistant has no provider_id"
        assert provider.api_base, "Dev Assistant provider has no api_base"
        assert "litellm" in provider.api_base or "4000" in provider.api_base, (
            f"Dev Assistant provider api_base does not point to LiteLLM: {provider.api_base}"
        )

    def test_local_assistant_exists(self):
        """Local Assistant must exist and be linked to the local provider."""
        assistant = self.env["llm.assistant"].search(
            [("name", "=", "Local Assistant")]
        )
        assert assistant, "Local Assistant not found — check llm_providers.xml"
        provider = assistant.provider_id
        assert provider, "Local Assistant has no provider_id"
        assert provider.api_base, "Local Assistant provider has no api_base"
        assert "litellm" in provider.api_base or "4000" in provider.api_base, (
            f"Local Assistant provider api_base does not point to LiteLLM: {provider.api_base}"
        )

    def test_both_assistants_use_litellm_service_type(self):
        """Both assistants must use service='openai' (pointing at LiteLLM)."""
        for name in ("Dev Assistant", "Local Assistant"):
            assistant = self.env["llm.assistant"].search([("name", "=", name)])
            if not assistant:
                continue
            provider = assistant.provider_id
            assert provider.service == "openai", (
                f"{name} provider service must be 'openai' (LiteLLM compat), got '{provider.service}'"
            )
