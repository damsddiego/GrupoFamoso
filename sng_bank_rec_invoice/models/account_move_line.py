from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    sng_invoice_sequence = fields.Char(
        string="Número de factura",
        compute="_compute_sng_invoice_sequence",
        help="Secuencia interna de la factura, nota de crédito o recibo relacionado.",
    )

    @api.depends("move_id.name", "move_id.move_type")
    def _compute_sng_invoice_sequence(self):
        for line in self:
            line.sng_invoice_sequence = (
                line.move_id.name
                if line.move_id.is_invoice(include_receipts=True)
                else False
            )
