# -*- coding: utf-8 -*-

from odoo import fields, models


class CustomerArReportWizard(models.TransientModel):
    _name = 'customer.ar.report.wizard'
    _description = 'Wizard — Reporte CxC por Cliente'

    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente')
    only_with_balance = fields.Boolean(
        string='Solo con saldo pendiente', default=False)

    def action_view_report(self):
        """Open the CxC report with a domain built from wizard fields."""
        self.ensure_one()
        domain = []

        if self.date_from:
            domain.append(('invoice_date_max', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date_min', '<=', self.date_to))
        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.only_with_balance:
            domain.append(('amount_due', '>', 0))

        return {
            'name': 'Reporte CxC por Cliente',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.ar.report',
            'view_mode': 'list,pivot',
            'domain': domain,
            'context': dict(self.env.context),
            'target': 'current',
        }
