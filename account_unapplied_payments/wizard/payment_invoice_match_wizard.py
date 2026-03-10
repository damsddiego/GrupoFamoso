from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PaymentInvoiceMatchWizard(models.TransientModel):
    _name = 'payment.invoice.match.wizard'
    _description = 'Apply payment to invoice'

    payment_id = fields.Many2one('account.payment', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', related='payment_id.partner_id', store=False, readonly=True
    )
    payment_type = fields.Selection(related='payment_id.payment_type', readonly=True)
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        domain="""
            [
                ('partner_id', '=', partner_id),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid')
            ]
        """,
        required=True,
    )
    amount_unapplied = fields.Monetary(
        string='Importe pendiente del pago', related='payment_id.unapplied_amount', readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency', related='payment_id.currency_id', store=False, readonly=True
    )
    invoice_amount_residual = fields.Monetary(
        string='Saldo pendiente de la factura',
        compute='_compute_invoice_amount_residual',
        currency_field='currency_id',
    )

    @api.depends('move_id', 'move_id.amount_residual')
    def _compute_invoice_amount_residual(self):
        for wizard in self:
            if wizard.move_id:
                wizard.invoice_amount_residual = abs(wizard.move_id.amount_residual)
            else:
                wizard.invoice_amount_residual = 0.0

    def action_apply(self):
        self.ensure_one()
        payment = self.payment_id
        invoice = self.move_id

        # Validaciones básicas
        if not payment or not invoice:
            raise UserError(_('Selecciona un pago y una factura.'))
        if payment.state != 'posted':
            raise UserError(_('Solo puedes aplicar pagos publicados.'))
        if invoice.state != 'posted':
            raise UserError(_('Solo puedes aplicar facturas publicadas.'))
        if payment.partner_id != invoice.partner_id:
            raise UserError(_('El pago y la factura deben tener el mismo cliente/proveedor.'))

        # Validación de tipo de pago vs tipo de factura
        if payment.payment_type == 'inbound' and invoice.move_type not in ('out_invoice', 'in_refund'):
            raise UserError(_('Un pago recibido solo puede aplicarse a facturas de cliente o notas de crédito de proveedor.'))
        if payment.payment_type == 'outbound' and invoice.move_type not in ('in_invoice', 'out_refund'):
            raise UserError(_('Un pago enviado solo puede aplicarse a facturas de proveedor o notas de crédito de cliente.'))

        # Validación de moneda
        if payment.currency_id != invoice.currency_id:
            raise UserError(_('El pago y la factura deben tener la misma moneda. Pago: %s, Factura: %s') % (
                payment.currency_id.name, invoice.currency_id.name
            ))

        # Buscar líneas para conciliar
        pay_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.reconcile and not l.reconciled
        )
        invoice_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.reconcile and not l.reconciled
        )
        account_ids = invoice_lines.mapped('account_id')
        pay_lines = pay_lines.filtered(lambda l: l.account_id in account_ids)
        invoice_lines = invoice_lines.filtered(lambda l: l.account_id in pay_lines.mapped('account_id'))

        if not pay_lines or not invoice_lines:
            raise UserError(_('No hay líneas pendientes para conciliar.'))

        # Realizar la conciliación
        (pay_lines | invoice_lines).reconcile()

        # Mensaje de éxito
        message = _('Pago aplicado exitosamente a la factura %s.') % invoice.name
        if payment.unapplied_amount > 0:
            message += _(' Queda un saldo pendiente de %s %s en el pago.') % (
                payment.unapplied_amount, payment.currency_id.symbol or payment.currency_id.name
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment',
                    'view_mode': 'form',
                    'res_id': payment.id,
                    'target': 'current',
                    'context': {'create': False},
                },
            }
        }
