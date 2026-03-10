from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    shipping_method = fields.Char(
        string='Método de envío',
        required=False,
        help='Método de envío para esta factura',
        readonly=True
    )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Copiar shipping_method al reversar una factura"""
        reverse_moves = super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)
        for move, reverse_move in zip(self, reverse_moves):
            if move.shipping_method:
                reverse_move.shipping_method = move.shipping_method
        return reverse_moves
