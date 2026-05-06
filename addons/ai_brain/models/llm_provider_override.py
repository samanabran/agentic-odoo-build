from openai import OpenAI

from odoo import fields, models


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    # Re-declare with admin-only group so non-admin users cannot read the
    # raw virtual key or internal LiteLLM URL via XML-RPC or the form view.
    # Server-side code must call self.sudo() before accessing these fields.
    api_key = fields.Char(groups="base.group_system")
    api_base = fields.Char(groups="base.group_system")

    def openai_get_client(self):
        # sudo() lets this server-side method read the restricted fields
        # regardless of the calling user's group. Without it, api_key would
        # be False for non-admin users, causing a silent 401 from LiteLLM.
        record = self.sudo()
        return OpenAI(api_key=record.api_key, base_url=record.api_base or None)