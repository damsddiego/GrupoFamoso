# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class SngGenerateCommissionWiz(models.TransientModel):
    _name = 'sng.generate.commission.wiz'
    _description = 'Generar Comisiones Mensuales'

    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        domain="[('is_salesperson', '=', True)]",
        help='Dejar vacío para procesar todos los vendedores.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('La fecha "Desde" no puede ser mayor a la fecha "Hasta".'))

        # El rango filtra por fecha de confirmación; los pagos antiguos sin
        # sellar (sng_confirmation_date vacío) caen por su fecha contable.
        domain = [
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ('in_process', 'paid')),
            ('company_id', '=', self.company_id.id),
            '|',
                '&',
                    ('sng_confirmation_date', '>=', self.date_from),
                    ('sng_confirmation_date', '<=', self.date_to),
                '&', '&',
                    ('sng_confirmation_date', '=', False),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
        ]
        payments = self.env['account.payment'].search(domain)
        if not payments:
            raise UserError(_('No se encontraron pagos en el rango y compañía seleccionados.'))

        for payment in payments:
            payment._generate_commission_lines()

        # Recuperamos las comisiones mensuales de los pagos procesados.
        lines = self.env['sng.commission.payment.line'].search([
            ('payment_id', 'in', payments.ids),
        ])
        monthlies = lines.mapped('monthly_id')
        if self.salesperson_id:
            monthlies = monthlies.filtered(lambda m: m.salesperson_id == self.salesperson_id)

        if not monthlies:
            raise UserError(_(
                'No se generaron comisiones. Verifique que exista un cuadro de comisiones (tramos) '
                'para la compañía y que los pagos tengan vendedor asignado.'
            ))

        action = self.env['ir.actions.actions']._for_xml_id(
            'sng_sales_commission_payment.action_sng_commission_monthly'
        )
        action['domain'] = [('id', 'in', monthlies.ids)]
        return action
