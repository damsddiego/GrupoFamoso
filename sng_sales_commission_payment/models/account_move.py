# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sng_commission_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'invoice_id',
        string='Detalle de Comisión del Pago',
        readonly=True,
        copy=False,
        groups='sales_commission_omax.group_sales_commission_user',
    )

    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        self._sng_unlink_draft_commission_lines()
        return res

    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        self._sng_unlink_draft_commission_lines()
        return res

    def _sng_unlink_draft_commission_lines(self):
        """Elimina el detalle de comisión de meses aún en borrador y recalcula.

        Se usa sudo() para que un usuario de contabilidad sin permisos sobre los
        modelos de comisión pueda pasar una factura a borrador o cancelarla.
        """
        lines = self.sudo().sng_commission_line_ids.filtered(lambda l: l.monthly_id.state == 'draft')
        monthlies = lines.mapped('monthly_id')
        lines.unlink()
        monthlies._recompute_commission()
