# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SngCloseCommissionWiz(models.TransientModel):
    _name = 'sng.close.commission.wiz'
    _description = 'Cerrar Comisiones del Mes por Compañía'

    period = fields.Date(
        string='Mes a Cerrar',
        required=True,
        help='Cualquier día del mes: se cierran todas las comisiones de ese mes.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    pending_count = fields.Integer(
        string='Comisiones Pendientes',
        compute='_compute_pending_count',
    )

    def _get_pending_monthlies(self):
        self.ensure_one()
        if not self.period:
            return self.env['sng.commission.monthly']
        return self.env['sng.commission.monthly'].search([
            ('company_id', '=', self.company_id.id),
            ('period', '=', self.period.replace(day=1)),
            ('state', '=', 'draft'),
        ])

    @api.depends('period', 'company_id')
    def _compute_pending_count(self):
        for wiz in self:
            wiz.pending_count = len(wiz._get_pending_monthlies()) if wiz.period else 0

    def action_close_month(self):
        self.ensure_one()
        monthlies = self._get_pending_monthlies()
        if not monthlies:
            raise UserError(_(
                'No hay comisiones pendientes para %(company)s en el mes seleccionado.',
                company=self.company_id.name,
            ))
        monthlies.action_close()

        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_sales_commission_payment.action_sng_commission_monthly'
        )
        action['domain'] = [('id', 'in', monthlies.ids)]
        action['context'] = {}
        return action
