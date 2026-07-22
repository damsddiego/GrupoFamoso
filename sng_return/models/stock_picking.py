from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sng_return_id = fields.Many2one(
        "sng.return",
        string="Devolución de cliente",
        index=True,
        check_company=True,
        help="Solicitud de devolución que originó esta recepción.",
    )
