from odoo import fields, models


class AiOriginMixin(models.AbstractModel):
    """
    Mixin that tags every Odoo record created or modified by AI (E5).

    Records inherit this mixin to make their AI-origin auditable and
    reversible. The `Revert AI changes from conversation X` server action
    uses these fields (implemented in M4).

    Usage:
        class SaleOrder(models.Model):
            _name = 'sale.order'
            _inherit = ['sale.order', 'ai.origin.mixin']
    """

    _name = "ai.origin.mixin"
    _description = "AI Origin Tracking Mixin"

    x_ai_origin_conversation_id = fields.Char(
        string="AI Conversation ID",
        index=True,
        help="ID of the ai.conversation that created or last modified this record.",
    )
    x_ai_origin_message_id = fields.Char(
        string="AI Message ID",
        index=True,
        help="ID of the ai.message whose tool call wrote this record.",
    )
    x_ai_created_at = fields.Datetime(
        string="AI Created At",
        readonly=True,
        help="Timestamp when AI first wrote to this record.",
    )
