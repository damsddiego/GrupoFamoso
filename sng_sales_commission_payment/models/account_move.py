# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sng_commission_line_ids = fields.One2many(
        'sng.commission.payment.line',
        'invoice_id',
        string='Líneas de Comisión del Pago',
        readonly=True,
        copy=False,
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
        for move in self:
            draft_lines = move.sng_commission_line_ids.filtered(lambda l: l.state == 'draft')
            if draft_lines:
                draft_lines.unlink()
