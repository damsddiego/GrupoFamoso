# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    """Añade al reporte Análisis de facturas el vendedor real de la factura:
    account.move.salesperson_id, un contacto con is_salesperson definido por
    sales_commission_omax (no el usuario de Odoo invoice_user_id)."""

    _inherit = "account.invoice.report"
    _depends = {"account.move": ["salesperson_id"]}

    salesperson_id = fields.Many2one(
        "res.partner",
        string="Vendedor (Contacto)",
        readonly=True,
        help="Vendedor asignado a la factura para comisiones "
             "(contacto, no usuario de Odoo).",
    )

    @api.model
    def _select(self) -> SQL:
        # El alias «move» (account_move) ya viene unido en el FROM base.
        return SQL("%s, move.salesperson_id AS salesperson_id", super()._select())
