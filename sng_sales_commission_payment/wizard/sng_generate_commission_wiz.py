# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class SngGenerateCommissionWiz(models.TransientModel):
    _name = 'sng.generate.commission.wiz'
    _description = 'Generar Comisiones Masivamente'

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
    replace_existing_draft = fields.Boolean(
        string='Reemplazar comisiones en borrador',
        default=False,
        help='Si está marcado, elimina las líneas de comisión en borrador existentes de los pagos seleccionados y las vuelve a calcular.',
    )

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('La fecha "Desde" no puede ser mayor a la fecha "Hasta".'))

        domain = [
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        payments = self.env['account.payment'].search(domain)
        if not payments:
            raise UserError(_('No se encontraron pagos en el rango y compañía seleccionados.'))

        generated = 0
        for payment in payments:
            if self.replace_existing_draft:
                draft_lines = payment.sng_commission_line_ids.filtered(lambda l: l.state == 'draft')
                draft_lines.unlink()
            payment._generate_commission_lines()
            generated += len(payment.sng_commission_line_ids)

        # Filtrar por vendedor si se especificó.
        lines = self.env['sng.commission.payment.line'].search([
            ('payment_id', 'in', payments.ids),
        ])
        if self.salesperson_id:
            lines = lines.filtered(lambda l: l.salesperson_id == self.salesperson_id)

        if not lines:
            raise UserError(_(
                'No se generaron comisiones. Verifique que existan configuraciones de comisión vigentes para los vendedores de los pagos en el rango seleccionado.'
            ))

        action = self.env['ir.actions.actions']._for_xml_id('sng_sales_commission_payment.action_sng_commission_payment_line')
        action['domain'] = [('id', 'in', lines.ids)]
        action['context'] = {'search_default_group_by_salesperson': 1}
        return action
