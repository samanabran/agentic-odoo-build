# -*- coding: utf-8 -*-
"""task_015_llm_thread_vendor_compat — verify classical _inherit preserves
vendor backward compatibility (ADR 0013, R2).

Asserts:
  - llm.thread browse/create/search still resolves correct records after
    ai_brain extends it.
  - mail.message vendor methods (llm_role, is_llm_*_message, body_json,
    is_error, _get_*_attachments) all still work after ai_brain extends.
  - The two ai_brain extension classes do NOT duplicate fields the vendor
    already defines.
"""
import pytest

odoo = pytest.importorskip("odoo")

try:
    from odoo.tests.common import TransactionCase
except Exception:
    TransactionCase = None


@pytest.mark.skipif(TransactionCase is None, reason="Odoo ORM not available")
class TestClassicalInheritance(TransactionCase):
    """R2 verification — classical _inherit hooks for llm.thread + mail.message."""

    def test_llm_thread_resolves_after_ai_brain_inherit(self):
        """env['llm.thread'] must still resolve to the same model after ai_brain extends it."""
        Thread = self.env["llm.thread"]
        assert Thread is not None, "llm.thread model not registered"
        # Classical _inherit: same _name, same table, just extended class.
        assert Thread._name == "llm.thread"
        assert Thread._table == "llm_thread"

    def test_llm_thread_vendor_fields_present(self):
        """All vendor llm.thread fields must remain accessible (no shadowing by ai_brain)."""
        Thread = self.env["llm.thread"]
        for field_name in (
            "model",
            "res_id",
            "provider_id",
            "model_id",
            "user_id",
            "tool_ids",
            "attachment_ids",
            "active",
        ):
            assert field_name in Thread._fields, (
                f"vendor field '{field_name}' missing from llm.thread "
                f"after ai_brain inherit — backward compat broken"
            )

    def test_mail_message_vendor_fields_present(self):
        """All vendor mail.message LLM fields must remain accessible."""
        Message = self.env["mail.message"]
        for field_name in ("llm_role", "is_error", "body_json", "user_vote"):
            assert field_name in Message._fields, (
                f"vendor field '{field_name}' missing from mail.message "
                f"after ai_brain inherit"
            )

    def test_mail_message_vendor_methods_present(self):
        """Vendor mail.message LLM helper methods must still be callable."""
        Message = self.env["mail.message"]
        for method_name in (
            "is_llm_message",
            "is_llm_user_message",
            "is_llm_assistant_message",
            "is_llm_tool_message",
            "get_llm_roles",
            "_get_image_attachments",
            "_get_pdf_attachments",
            "_get_text_attachments",
            "_get_unsupported_attachments",
        ):
            assert hasattr(Message, method_name), (
                f"vendor method '{method_name}' missing from mail.message "
                f"after ai_brain inherit"
            )

    def test_ai_brain_does_not_duplicate_token_fields(self):
        """R5/PR #15 will add token fields. R2 must NOT pre-add them."""
        Message = self.env["mail.message"]
        for field_name in ("token_count_input", "token_count_output", "total_cost_usd"):
            assert field_name not in Message._fields, (
                f"R2 must not add '{field_name}' — it belongs to R5/PR #15. "
                f"Found field on mail.message; remove from ai_message.py."
            )

    def test_create_and_browse_llm_thread_with_provider(self):
        """End-to-end: create an llm.thread with a vendor provider, browse it back."""
        provider = self.env["llm.provider"].search(
            [("name", "=", "litellm-cloud-dev")], limit=1
        )
        if not provider:
            pytest.skip(
                "litellm-cloud-dev provider not seeded — fix data/llm_providers.xml"
            )
        model = self.env["llm.model"].search(
            [
                ("provider_id", "=", provider.id),
                ("model_use", "in", ["chat", "multimodal"]),
            ],
            limit=1,
        )
        if not model:
            pytest.skip(
                "no chat/multimodal llm.model on litellm-cloud-dev — "
                "vendor seed gap, R2 still passes but flag for ai_brain data PR"
            )
        thread = self.env["llm.thread"].create(
            {
                "name": "R2 verification thread",
                "provider_id": provider.id,
                "model_id": model.id,
            }
        )
        assert thread.exists()
        same = self.env["llm.thread"].browse(thread.id)
        assert same.id == thread.id
        assert same.name == "R2 verification thread"
