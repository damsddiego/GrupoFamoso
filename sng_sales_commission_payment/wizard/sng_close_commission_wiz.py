# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SngCloseCommissionWiz(models.TransientModel):
    _name = 'sng.close.commission.wiz'
    _description = 'Cerrar Comisiones del Mes por Cuadro'

    period = fields.Date(
        string='Mes a Cerrar',
        required=True,
        help='Cualquier día del mes: se cierran todas las comisiones de ese mes.',
    )
    scheme_id = fields.Many2one(
        'sng.commission.scheme',
        string='Cuadro',
        required=True,
        default=lambda self: self._default_scheme_id(),
        context={'active_test': False},
        help='Se cierran las comisiones de todas las compañías del cuadro.',
    )
    company_names = fields.Char(
        related='scheme_id.company_names',
        string='Compañías',
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

    @api.model
    def _default_scheme_id(self):
        return self.env['sng.commission.scheme']._get_for_company(
            self.env.company, fields.Date.context_today(self))

    @api.onchange('period')
    def _onchange_period(self):
        """Propone el cuadro que rige en ese mes para la compañía actual."""
        if self.period:
            scheme = self.env['sng.commission.scheme']._get_for_company(self.env.company, self.period)
            if scheme:
                self.scheme_id = scheme

    def _get_bounds(self):
        self.ensure_one()
        return self.env['sng.commission.monthly']._sng_period_bounds(self.period)

    def _get_pending_monthlies(self):
        self.ensure_one()
        if not self.period:
            return self.env['sng.commission.monthly']
        return self.env['sng.commission.monthly'].search([
            ('scheme_id', '=', self.scheme_id.id),
            ('period', '=', self.period.replace(day=1)),
            ('state', '=', 'draft'),
        ])

    @api.depends('period', 'scheme_id')
    def _compute_pending_count(self):
        for wiz in self:
            wiz.pending_count = len(wiz._get_pending_monthlies()) if wiz.period else 0

    @api.depends('period', 'scheme_id')
    def _compute_uncommissioned(self):
        Monthly = self.env['sng.commission.monthly']
        for wiz in self:
            rows = []
            if wiz.period and wiz.scheme_id:
                first, last = wiz._get_bounds()
                for company in wiz.scheme_id.sudo().company_ids:
                    rows += Monthly._sng_find_uncommissioned(company, first, last)
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
        for company in self.scheme_id.sudo().company_ids:
            Monthly._sng_generate_pending(company, first, last)
        monthlies = self._get_pending_monthlies()
        if not monthlies:
            raise UserError(_(
                'No hay comisiones pendientes del cuadro %(scheme)s en el mes seleccionado.',
                scheme=self.scheme_id.name,
            ))
        monthlies.action_close()

        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_sales_commission_payment.action_sng_commission_monthly'
        )
        action['domain'] = [('id', 'in', monthlies.ids)]
        action['context'] = {}
        return action
