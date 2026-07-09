# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockAdjustmentRejectWizard(models.TransientModel):
    _name = 'stock.adjustment.reject.wizard'
    _description = 'Wizard para Rechazar Solicitud de Ajuste'

    request_id = fields.Many2one(
        'stock.adjustment.request',
        string='Solicitud',
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        required=True,
    )

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.rejection_reason:
            raise UserError(_('Debe indicar el motivo de rechazo.'))
        self.request_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason,
        })
        self.request_id.message_post(
            body=_('Solicitud rechazada. Motivo: %s') % self.rejection_reason,
        )
        return {'type': 'ir.actions.act_window_close'}
