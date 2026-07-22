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

    def action_create_bills(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise UserError(_('Debe seleccionar al menos una comisión mensual.'))

        monthlies = self.env['sng.commission.monthly'].browse(active_ids)
        to_bill = monthlies.filtered(lambda m: m.state == 'draft' and m.commission_amount > 0)
        if not to_bill:
            raise UserError(_('No hay comisiones pendientes (con monto) para facturar.'))

        commission_product = self.env.ref('sng_sales_commission_payment.sng_sales_commission_product')
        bill_ids = self.env['account.move']

        # Una factura de compra por vendedor, con una línea por mes.
        for salesperson, months in to_bill.grouped('salesperson_id').items():
            bill = self._create_bill(salesperson, months, commission_product)
            if bill:
                bill_ids += bill
                months.write({'bill_id': bill.id})

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

    def _create_bill(self, salesperson, months, commission_product):
        self.ensure_one()
        if not salesperson:
            raise UserError(_('No se puede generar una factura de compra sin vendedor.'))

        invoice_lines = []
        for month in months:
            line_vals = {
                'product_id': commission_product.id,
                'name': month.name or _('Comisión %s', month.period_label),
                'quantity': 1,
                'product_uom_id': commission_product.uom_id.id,
                'price_unit': month.commission_amount,
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
