# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class SngCommissionPaymentLine(models.Model):
    _name = 'sng.commission.payment.line'
    _description = 'Línea de Comisión por Pago'
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Descripción',
        compute='_compute_name',
        store=True,
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        required=True,
        index=True,
        ondelete='cascade',
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        index=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='payment_id.partner_id',
        store=True,
        index=True,
    )
    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        required=True,
        domain="[('is_salesperson', '=', True)]",
        index=True,
    )
    payment_date = fields.Date(
        string='Fecha de Pago',
        related='payment_id.date',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='payment_id.company_id',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='payment_id.currency_id',
        store=True,
    )
    payment_amount = fields.Monetary(
        string='Monto del Pago Aplicado',
        currency_field='currency_id',
        required=True,
    )
    invoice_amount_untaxed = fields.Monetary(
        string='Monto Sin Impuestos Factura',
        currency_field='currency_id',
        required=True,
    )
    invoice_amount_total = fields.Monetary(
        string='Monto Total Factura',
        currency_field='currency_id',
        required=True,
    )
    commission_base = fields.Monetary(
        string='Base de Comisión',
        currency_field='currency_id',
        required=True,
        help='Monto sin impuestos pagado proporcionalmente por este pago.',
    )
    commission_percentage = fields.Float(
        string='% Comisión',
        required=True,
    )
    commission_amount = fields.Monetary(
        string='Monto de Comisión',
        currency_field='currency_id',
        required=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Pendiente'),
            ('billed', 'Facturado'),
            ('paid', 'Pagado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        index=True,
    )
    bill_id = fields.Many2one(
        'account.move',
        string='Factura de Comisión',
        index=True,
        ondelete='set null',
    )

    @api.depends('commission_percentage', 'salesperson_id', 'invoice_id')
    def _compute_name(self):
        for line in self:
            line.name = _(
                "Comisión %(percentage).2f%% - %(salesperson)s - Factura %(invoice)s",
                percentage=line.commission_percentage,
                salesperson=line.salesperson_id.name or '',
                invoice=line.invoice_id.name or '',
            )
