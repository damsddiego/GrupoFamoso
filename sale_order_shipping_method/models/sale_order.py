from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shipping_method = fields.Char(
        string='Método de envío',
        required=False,
        help='Método de envío para este pedido de venta',
        states={'sale': [('readonly', True)], 'done': [('readonly', True)], 'cancel': [('readonly', True)]}
    )

    def _prepare_invoice(self):
        """Copiar shipping_method a la factura"""
        invoice_vals = super()._prepare_invoice()
        if self.shipping_method:
            invoice_vals['shipping_method'] = self.shipping_method
        return invoice_vals
