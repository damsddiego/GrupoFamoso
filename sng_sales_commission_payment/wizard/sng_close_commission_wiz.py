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
    uncommissioned_payment_count = fields.Integer(
        string='Pagos sin comisión generada',
        compute='_compute_uncommissioned',
        help='Cobros confirmados en el mes, aplicados a facturas, que todavía no '
             'tienen línea de comisión. Se generan automáticamente al cerrar.',
    )
    uncommissioned_pair_count = fields.Integer(
        string='Pares pago/factura sin comisión',
        compute='_compute_uncommissioned',
    )
    no_salesperson_invoice_count = fields.Integer(
        string='Facturas sin vendedor',
        compute='_compute_uncommissioned',
        help='Facturas cobradas en el mes sin vendedor en la factura ni en el '
             'cliente: no generan comisión hasta que se les asigne uno.',
    )
    no_salesperson_invoice_ids = fields.Many2many(
        'account.move',
        compute='_compute_uncommissioned',
    )

    def _get_bounds(self):
        self.ensure_one()
        return self.env['sng.commission.monthly']._sng_period_bounds(self.period)

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

    @api.depends('period', 'company_id')
    def _compute_uncommissioned(self):
        Monthly = self.env['sng.commission.monthly']
        for wiz in self:
            if not wiz.period or not wiz.company_id:
                rows = []
            else:
                first, last = wiz._get_bounds()
                rows = Monthly._sng_find_uncommissioned(wiz.company_id, first, last)
            generable = [r for r in rows if r['salesperson_id']]
            orphan_invoice_ids = sorted({r['invoice_id'] for r in rows if not r['salesperson_id']})
            wiz.uncommissioned_pair_count = len(generable)
            wiz.uncommissioned_payment_count = len({r['payment_id'] for r in generable})
            wiz.no_salesperson_invoice_count = len(orphan_invoice_ids)
            wiz.no_salesperson_invoice_ids = [(6, 0, orphan_invoice_ids)]

    def action_view_no_salesperson_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas cobradas sin vendedor'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.no_salesperson_invoice_ids.ids)],
            'context': {'create': False},
        }

    def action_close_month(self):
        self.ensure_one()
        first, last = self._get_bounds()
        Monthly = self.env['sng.commission.monthly']
        # Primero se generan los cobros del mes que aún no tienen comisión:
        # pueden crear comisiones mensuales nuevas (vendedores sin registro).
        Monthly._sng_generate_pending(self.company_id, first, last)
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
