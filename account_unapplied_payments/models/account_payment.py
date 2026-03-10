from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    unapplied_amount = fields.Monetary(
        string='Importe pendiente',
        currency_field='currency_id',
        compute='_compute_unapplied_amount',
        compute_sudo=True,
        store=True,
    )
    unapplied = fields.Boolean(
        string='No aplicado',
        compute='_compute_unapplied_amount',
        compute_sudo=True,
        store=True,
    )

    @api.depends(
        'state',
        'move_id',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.amount_residual_currency',
        'move_id.line_ids.reconciled',
        'move_id.line_ids.matched_debit_ids',
        'move_id.line_ids.matched_credit_ids',
        'move_id.line_ids.account_id',
        'move_id.line_ids.currency_id',
        'move_id.line_ids.partner_id',
        'partner_id',
    )
    def _compute_unapplied_amount(self):
        for payment in self:
            if payment.state != 'posted' or not payment.move_id:
                payment.unapplied_amount = 0.0
                payment.unapplied = False
                continue
            residual = 0.0
            lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.reconcile
                and l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )
            for line in lines:
                residual += abs(
                    line.amount_residual_currency if line.currency_id else line.amount_residual
                )
            payment.unapplied_amount = residual
            if payment.currency_id:
                payment.unapplied = not payment.currency_id.is_zero(residual)
            else:
                payment.unapplied = bool(residual)

    def action_open_apply_invoice_wizard(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_('Solo puedes aplicar pagos publicados.'))
        return {
            'name': _('Aplicar pago a factura'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.invoice.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_id': self.id,
            },
        }
