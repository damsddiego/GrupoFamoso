from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    sng_return_id = fields.Many2one(
        "sng.return",
        string="Devolución de origen",
        index=True,
        copy=False,
        readonly=True,
        help="Devolución de cliente que generó esta nota de crédito.",
    )
    sng_return_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén de devolución",
        related="sng_return_id.warehouse_id",
        store=True,
        readonly=True,
    )
    sng_return_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación destino",
        related="sng_return_id.location_dest_id",
        store=True,
        readonly=True,
    )
    sng_return_picking_id = fields.Many2one(
        "stock.picking",
        string="Recepción de devolución",
        related="sng_return_id.picking_id",
        store=True,
        readonly=True,
    )
