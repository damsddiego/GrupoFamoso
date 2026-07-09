# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class SngCreateCommissionBillWiz(models.TransientModel):
    _name = 'sng.create.commission.bill.wiz'
    _description = 'Generar Factura de Comisión'

    date = fields.Date(
        string='Fecha de Factura',
        required=True,
        default=fields.Date.context_today,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta Contable',
        help='Cuenta de gasto a usar en la factura de compra. Si se deja vacío se usa la cuenta del producto.',
    )
    group_by_salesperson = fields.Boolean(
        string='Agrupar por Vendedor',
        default=True,
        help='Crea una factura de compra por cada vendedor.',
    )

    def action_create_bills(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise UserError(_('Debe seleccionar al menos una línea de comisión.'))

        commission_lines = self.env['sng.commission.payment.line'].browse(active_ids)
        draft_lines = commission_lines.filtered(lambda l: l.state == 'draft')
        if not draft_lines:
            raise UserError(_('No hay líneas de comisión pendientes para facturar.'))

        if not self.group_by_salesperson and len(draft_lines) > 1:
            raise UserError(_('Sin agrupar por vendedor solo se puede facturar una línea a la vez.'))

        commission_product = self.env.ref('sng_sales_commission_payment.sng_sales_commission_product')
        bill_ids = self.env['account.move']

        if self.group_by_salesperson:
            grouped = draft_lines.grouped('salesperson_id')
            for salesperson, lines in grouped.items():
                bill = self._create_bill_for_salesperson(salesperson, lines, commission_product)
                if bill:
                    bill_ids += bill
                    lines.write({'state': 'billed', 'bill_id': bill.id})
        else:
            line = draft_lines[0]
            bill = self._create_bill_for_salesperson(line.salesperson_id, line, commission_product)
            if bill:
                bill_ids += bill
                line.write({'state': 'billed', 'bill_id': bill.id})

        if not bill_ids:
            raise UserError(_('No se pudo generar ninguna factura de compra.'))

        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_in_invoice_type')
        if len(bill_ids) > 1:
            action['domain'] = [('id', 'in', bill_ids.ids)]
            action['views'] = [(False, 'list'), (False, 'form')]
        else:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = bill_ids.id
        return action

    def _create_bill_for_salesperson(self, salesperson, lines, commission_product):
        self.ensure_one()
        if not salesperson:
            raise UserError(_('No se puede generar una factura de compra sin vendedor.'))

        total_amount = sum(lines.mapped('commission_amount'))
        if total_amount <= 0:
            return False

        invoice_lines = []
        for line in lines:
            line_vals = {
                'product_id': commission_product.id,
                'name': line.name or _('Comisión por pago %s', line.payment_id.name),
                'quantity': 1,
                'product_uom_id': commission_product.uom_id.id,
                'price_unit': line.commission_amount,
            }
            if self.account_id:
                line_vals['account_id'] = self.account_id.id
            invoice_lines.append((0, 0, line_vals))

        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': salesperson.id,
            'invoice_date': self.date,
            'date': self.date,
            'company_id': self.company_id.id,
            'invoice_line_ids': invoice_lines,
        }
        return self.env['account.move'].create(bill_vals)
