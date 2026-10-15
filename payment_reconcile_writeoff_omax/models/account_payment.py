# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


_logger = logging.getLogger(__name__)


TEMP_PAYMENT_COMPANY_CHECK_BYPASS_DATES = {
    date(2026, 5, 26),
    date(2026, 5, 27),
}
TEMP_PAYMENT_COMPANY_CHECK_BYPASS_COMPANY_ID = 2
TEMP_PAYMENT_COMPANY_CHECK_BYPASS_FIELDS = {"partner_id"}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    outstanding_move_lines = fields.One2many('outstanding.account.move', 'pyament_id', string="Moves")
    pay_moves = fields.Boolean('Pay Moves', copy=0)
    writeoff_amt = fields.Float(string='Writeoff Amount')
    writeoff_account_id = fields.Many2one(comodel_name='account.account', string="Writeoff Account", copy=False, domain="[('deprecated', '=', False)]", 
        check_company=True)
    writeoff_notes = fields.Char('Writeoff Notes')
    outstanding_not_payable_names = fields.Char(
        string='Documentos seleccionados sin saldo',
        compute='_compute_outstanding_not_payable_names',
        help="Facturas marcadas para pagar que ya no tienen saldo pendiente "
             "(fueron pagadas con otro pago o anuladas).",
    )

    @api.depends('outstanding_move_lines.select_to_pay', 'outstanding_move_lines.is_payable')
    def _compute_outstanding_not_payable_names(self):
        for payment in self:
            bad = payment._get_selected_not_payable_lines()
            payment.outstanding_not_payable_names = ', '.join(bad.mapped('display_name')) or False

    def _get_selected_not_payable_lines(self):
        """Lineas marcadas para pagar cuyo documento ya no se puede aplicar."""
        self.ensure_one()
        return self.outstanding_move_lines.filtered(
            lambda l: l.select_to_pay and not l.is_payable
        )

    def _check_selected_outstanding_moves(self):
        """Falla con un mensaje claro si alguna factura marcada ya no tiene saldo.

        Sin esta validacion el error aparecia mas adelante como
        "No Outstanding Account found", que apunta a la configuracion del
        diario cuando el problema real es la factura.
        """
        for payment in self.filtered('pay_moves'):
            bad = payment._get_selected_not_payable_lines()
            if bad:
                raise UserError(_(
                    "No se puede confirmar el pago %(payment)s porque estas facturas "
                    "marcadas ya no tienen saldo pendiente (fueron pagadas con otro "
                    "pago o anuladas):\n%(docs)s\n\n"
                    "Desmárquelas o use el botón «Recargar pendientes» para "
                    "actualizar la lista.",
                    payment=payment.display_name or payment.memo or payment.id,
                    docs='\n'.join('- %s' % name for name in bad.mapped('display_name')),
                ))

    def _check_company(self, fnames=None):
        today = fields.Date.context_today(self)
        if today not in TEMP_PAYMENT_COMPANY_CHECK_BYPASS_DATES:
            return super()._check_company(fnames=fnames)

        bypass_payments = self.filtered(
            lambda payment: payment.company_id.id == TEMP_PAYMENT_COMPANY_CHECK_BYPASS_COMPANY_ID
        )
        regular_payments = self - bypass_payments

        if regular_payments:
            super(AccountPayment, regular_payments)._check_company(fnames=fnames)

        if not bypass_payments:
            return

        if fnames is None or {"company_id", "company_ids"} & set(fnames):
            checked_fields = set(self._fields)
        else:
            checked_fields = set(fnames)

        remaining_fields = list(checked_fields - TEMP_PAYMENT_COMPANY_CHECK_BYPASS_FIELDS)
        if remaining_fields:
            super(AccountPayment, bypass_payments)._check_company(fnames=remaining_fields)

        _logger.warning(
            "Temporary company check bypass applied on %s for account.payment "
            "ids %s in company %s. Skipped fields: %s",
            sorted(TEMP_PAYMENT_COMPANY_CHECK_BYPASS_DATES),
            bypass_payments.ids,
            TEMP_PAYMENT_COMPANY_CHECK_BYPASS_COMPANY_ID,
            sorted(TEMP_PAYMENT_COMPANY_CHECK_BYPASS_FIELDS),
        )

    def _search_outstanding_moves(self):
        """Documentos abiertos del tercero que este pago podria aplicar."""
        self.ensure_one()
        move_type = ['out_invoice'] if self.payment_type == 'inbound' else ['in_invoice']
        return self.env["account.move"].search([
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('move_type', 'in', move_type),
            ('amount_residual', '!=', 0),
            ('currency_id', '=', self.currency_id.id),
        ], order='invoice_date')

    def _load_outstanding_moves(self, keep_selection=False):
        """Populate outstanding_move_lines with open documents for the partner.

        Con ``keep_selection`` se conservan marcadas las facturas que ya
        estaban seleccionadas y siguen con saldo; las que ya se pagaron por
        otro medio desaparecen de la lista.
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please select a partner before loading documents."))
        if not self.currency_id:
            raise UserError(_("Please select a currency before loading documents."))
        moves = self._search_outstanding_moves()
        if not moves:
            raise UserError(_("No posted invoices/bills with a residual amount were found for this partner."))

        selected_ids = set()
        if keep_selection:
            selected_ids = set(
                self.outstanding_move_lines.filtered('select_to_pay').mapped('account_move_id').ids
            )
        # Borrado explicito de las lineas anteriores (mas seguro que (5, 0, 0)
        # cuando se refrescan varios pagos en la misma transaccion).
        self.outstanding_move_lines.unlink()
        move_lines = []
        for move in moves:
            move_lines.append((0, 0, {
                'name': move.name,
                'account_move_id': move.id,
                'select_to_pay': move.id in selected_ids,
            }))
        if not keep_selection:
            # reset write-off suggestion but keep original payment amount (comes from external app)
            self.writeoff_amt = 0
        self.outstanding_move_lines = move_lines

    def _refresh_outstanding_moves(self):
        """Refresco silencioso de la lista conservando la seleccion.

        Se usa al volver un pago a borrador: entre tanto otras facturas
        pudieron pagarse con otro pago y deben salir de la lista para que la
        confirmacion no falle. Nunca lanza error; si no hay nada que mostrar
        deja la lista vacia.
        """
        for payment in self.filtered(lambda p: p.pay_moves and p.partner_id and p.currency_id):
            moves = payment._search_outstanding_moves()
            if moves:
                payment._load_outstanding_moves(keep_selection=True)
            else:
                payment.outstanding_move_lines.unlink()

    def action_reload_outstanding_moves(self):
        """Button to reload outstanding invoices/bills while in draft.

        Conserva la seleccion de las facturas que siguen con saldo.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("You can reload outstanding documents only in draft payments."))
        self.pay_moves = True
        self._load_outstanding_moves(keep_selection=True)
        return True

    #change lines selection then set 'Retencion Amount' as 0 and also change 'Amount' of payment
    @api.onchange('pay_moves', 'outstanding_move_lines')
    def _onchange_outstanding_move_lines(self):
        """When selecting invoices/bills to pay, keep the original payment amount
        (imported from external app) and only suggest/update the write-off amount
        as the difference between selected invoices and the fixed payment amount.
        """
        if self.pay_moves and self.outstanding_move_lines:
            outstanding_move_ids = self.outstanding_move_lines.filtered(lambda pl: pl.select_to_pay)
            if outstanding_move_ids and self.amount:
                total_invoice_amount = sum(outstanding_move_ids.mapped('amount_residual'))
                # Suggest write-off as positive difference (if any)
                self.writeoff_amt = max(0.0, total_invoice_amount - self.amount)
            else:
                self.writeoff_amt = 0.0

    #change 'Write-Off Amount' then change 'Amount' of payment and also manage warning based on Amount
    @api.onchange('writeoff_amt')
    def _onchange_line_writeoff_amounts(self):
        """Do not change the original payment amount when user edits write-off.
        Only validate the coherence between:
            sum(selected invoices)  vs  payment amount + write-off amount.
        """
        if self.pay_moves and self.outstanding_move_lines:
            outstanding_move_ids = self.outstanding_move_lines.filtered(lambda pl: pl.select_to_pay)
            if outstanding_move_ids:
                total_invoice_amount = sum(outstanding_move_ids.mapped('amount_residual'))
                payment_amount = self.amount or 0.0
                writeoff_amount = self.writeoff_amt or 0.0

                # If no write-off is set, allow difference so that remaining amount
                # stays as credit in favor of the customer/vendor.
                if writeoff_amount <= 0:
                    return

                # If a positive write-off is set, enforce strict equality.
                total_payment_and_writeoff = payment_amount + writeoff_amount
                if total_payment_and_writeoff != total_invoice_amount:
                    return {
                        'warning': {
                            'title': "Warning!",
                            'message': (
                                "The total of the selected invoices ({:.2f}) is not equal to "
                                "Payment amount ({:.2f}) + Write-off amount ({:.2f}) = {:.2f}."
                            ).format(
                                total_invoice_amount,
                                payment_amount,
                                writeoff_amount,
                                total_payment_and_writeoff,
                            ),
                        }
                    }

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if not self.partner_id:
            self.pay_moves = False
    
    @api.onchange('pay_moves')
    def _onchange_pay_moves(self):
        if self.pay_moves:
            self._load_outstanding_moves()

    #account/models/account_payment.py
    def _reconcile_selected_outstanding_moves(self):
        if self.is_reconciled:
            # Ya se aplicó a las facturas (p. ej. al confirmar); no hay nada
            # que re-conciliar.
            return
        if self.pay_moves:
            self._check_selected_outstanding_moves()
            outstanding_move_ids = self.outstanding_move_lines.filtered(lambda pl: pl.select_to_pay)
            total_invoice_amount = 0
            if outstanding_move_ids:
                total_invoice_amount = sum(outstanding_move_ids.mapped('amount_residual'))#amount_total 
                # Only enforce strict equality when a write-off account is configured.
                if self.writeoff_amt and self.writeoff_account_id:
                    total_payment_and_writeoff = self.amount + self.writeoff_amt
                    if total_payment_and_writeoff != total_invoice_amount:
                        doc_type = 'Invoices' if self.payment_type == 'inbound' else 'Bills'
                        raise UserError(
                                "Payment mismatch!\n\n"
                                "The total of the selected invoices is {:.2f}, but the sum of payment amount {:.2f} and write-off amount {:.2f} is {:.2f}.\n\n"
                                "Please make sure that the Payment Amount + Write-Off Amount equals the total due on the selected {}."
                                .format(total_invoice_amount, self.amount, self.writeoff_amt, total_payment_and_writeoff, doc_type)
                            )
            payment_amount = self.amount
            discount_amount = self.writeoff_amt
            writeoff_account_id = self.writeoff_account_id
            for outstanding_move_id in outstanding_move_ids:
                move = outstanding_move_id.account_move_id
                paid_amount = outstanding_move_id.amount_residual
                
                sign = 1 if move.is_outbound() else -1
                if self.pay_moves and move.invoice_outstanding_credits_debits_widget == False:
                    # Llegar aqui con una factura abierta significa que el pago
                    # no genero un credito pendiente aplicable (p. ej. la
                    # cuenta transitoria del metodo de pago no esta definida).
                    # El caso "factura ya pagada" se detecta antes, en
                    # _check_selected_outstanding_moves, con su propio mensaje.
                    tab = _("Pagos entrantes") if self.payment_type == 'inbound' else _("Pagos salientes")
                    raise UserError(_(
                        "No se encontró un crédito pendiente de este pago para aplicarlo "
                        "a la factura %(doc)s (saldo %(residual)s, estado de pago %(pstate)s).\n\n"
                        "Revise la cuenta transitoria del método de pago «%(method)s» en el "
                        "diario «%(journal)s» (Contabilidad → Configuración → Diarios → "
                        "pestaña %(tab)s).",
                        doc=move.name,
                        residual=move.amount_residual,
                        pstate=move.payment_state,
                        method=self.payment_method_line_id.name,
                        journal=self.journal_id.display_name,
                        tab=tab,
                    ))
                #if paid_amount
                for line in move.invoice_outstanding_credits_debits_widget.get('content'):
                    if line.get('account_payment_id') == self.id and self.is_reconciled == False and paid_amount:
                        opp_reconcile_id = line.get('id')
                        ln = self.env["account.move.line"].browse(opp_reconcile_id)
                        
                        discount_apply = False
                        ###discount
                        # Apply discount (write-off) only if a write-off account is configured.
                        if abs(ln.amount_residual_currency) < paid_amount and discount_amount > 0 and writeoff_account_id:
                            if move.move_type == 'in_invoice':##for vendor bill and Credit note
                                discount_amount = -1 * discount_amount
                            
                            #when inv then get ln.amount_residual_currency is negative
                            apply_discount_amount = abs(ln.amount_residual_currency) - paid_amount
                            
                            if abs(apply_discount_amount) > discount_amount:
                                apply_discount_amount = discount_amount
                            if move.move_type == 'in_invoice':#Bill
                                discount_amount -= apply_discount_amount
                            else:#INV
                                discount_amount -= abs(apply_discount_amount)

                            #update destination_account_line(receivable) to add dscount amount
                            #update payment -> move -> destination_account_line 
                            lines_to_reconcile = self.move_id.line_ids
                            move_receivable_line = lines_to_reconcile.filtered(lambda l: l.account_id == self.destination_account_id)
                            
                            if move.move_type == 'in_invoice':#Bill
                                update_balance = abs(apply_discount_amount) + move_receivable_line.balance
                                credit_balance = update_balance
                                update_balance = sign * update_balance#set + or - in balance, amount_currency and amount_residual_currency
                            else:#INV
                                #update_balance = apply_discount_amount + abs(move_receivable_line.balance)
                                update_balance = apply_discount_amount + move_receivable_line.balance
                                credit_balance = sign * update_balance
                                #update_balance = sign * update_balance#set + or - in balance, amount_currency and amount_residual_currency
                            self.env.cr.execute("""
                                UPDATE account_move_line
                                SET balance = %s,
                                    debit = %s,
                                    credit = %s,
                                    amount_currency = %s,
                                    amount_residual_currency = %s
                                WHERE id = %s
                            """, (
                                update_balance,
                                0,
                                credit_balance,
                                update_balance,
                                update_balance,
                                move_receivable_line.id
                            ))
                            #self.env.cr.commit()
                            
                            ##Add new Write-Off line
                            converted_balance = self.currency_id._convert(
                                apply_discount_amount,
                                self.company_id.currency_id,
                                self.company_id,
                                self.date
                            )
                            if move.move_type == 'out_invoice':#INV
                                apply_discount_amount = abs(apply_discount_amount)
                                converted_balance = abs(converted_balance)

                            self.env.cr.execute("""
                                INSERT INTO account_move_line
                                (name, account_id, partner_id, move_id, currency_id, amount_currency, balance, debit, company_id, date, create_uid, create_date, write_uid, write_date, display_type, parent_state, company_currency_id, amount_residual_currency, writeoff_notes)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (
                                'Write-Off',
                                writeoff_account_id.id,
                                self.move_id.partner_id.id if self.move_id.partner_id else None,
                                self.move_id.id,
                                self.move_id.currency_id.id if self.move_id.currency_id else None,
                                apply_discount_amount,
                                apply_discount_amount,
                                converted_balance,
                                self.company_id.id,
                                self.date,
                                self.env.uid,
                                self.env.uid,
                                'product',
                                self.move_id.state,
                                self.move_id.company_currency_id.id,
                                0,
                                self.writeoff_notes if self.writeoff_notes else '',
                                
                            ))

                            # Fetch the newly created ID
                            new_line_id = self.env.cr.fetchone()[0]
                            self.env.cr.commit()
                            new_line_rec = self.env['account.move.line'].browse(new_line_id)#.with_context(check_move_validity=False)
                            new_line_rec.reconcile()
                            move.js_assign_outstanding_line(new_line_id)
                            discount_apply = True

                            #call default compute to manage and updated value in amount_residual_currency field in receivable line
                            move_receivable_line._compute_amount_residual()
                        ###finish discount

                        ###normal without discount
                        if abs(ln.amount_residual_currency) > paid_amount:
                            amount_residual_currency = sign * paid_amount
                        else:
                            amount_residual_currency = ln.amount_residual_currency
                        
                        if abs(ln.amount_residual) > paid_amount:
                            amount_residual = sign * paid_amount
                        else:
                            amount_residual = ln.amount_residual
                        ln.amount_residual_currency = amount_residual_currency
                        if ln.currency_id != move.currency_id:
                                ln.amount_residual = amount_residual
                        else:
                            if ln.currency_id.id != self.company_id.currency_id.id:
                                amount_residual = ln.currency_id._convert(amount_residual, self.env.company.currency_id, self.company_id, self.date)
                                ln.amount_residual = amount_residual
                        move.js_assign_outstanding_line(opp_reconcile_id)
                        paid_amount -= abs(amount_residual)

    def action_validate(self):
        # Botón "Marcar como pagado": concilia las facturas seleccionadas y
        # deja que el core marque el pago como pagado (decisión explícita
        # del usuario).
        for rec in self:
            rec._reconcile_selected_outstanding_moves()
        return super().action_validate()

    def action_draft(self):
        res = super().action_draft()
        for rec in self:
            if rec.move_id and rec.pay_moves:
                rec.move_id.unlink()
        # Al borrar el asiento las facturas de este pago vuelven a quedar
        # abiertas; las que entre tanto se pagaron con otro pago salen de la
        # lista para que la proxima confirmacion no falle.
        self._refresh_outstanding_moves()
        return res

    def action_post(self):
        # Validar antes de que el core genere el asiento: asi el usuario ve
        # el motivo real y no se crea nada que luego haya que revertir.
        self._check_selected_outstanding_moves()
        res = super().action_post()
        # Puede venir con varios pagos (p. ej. "Registrar pago" masivo desde
        # la lista de facturas).
        for rec in self.filtered('pay_moves'):
            # Solo conciliar contra las facturas seleccionadas. El estado lo
            # decide el core: 'in_process' si el método usa cuenta transitoria
            # (queda pendiente de conciliar con el extracto) o 'paid' si la
            # cuenta es de efectivo.
            rec._reconcile_selected_outstanding_moves()
        return res

    def unlink(self):
        for rec in self:
            rec.outstanding_move_lines.unlink()
        return super(AccountPayment, self).unlink()

class OutStandingAccountMove(models.Model):
    _name = 'outstanding.account.move'
    _description = 'Outstanding Account Moves'
    _check_company_auto = True

    # ondelete='cascade': sin esto, el comando (5, 0, 0) del one2many intenta
    # poner pyament_id en NULL en vez de borrar las lineas y viola el NOT NULL.
    pyament_id = fields.Many2one('account.payment', string='Payment', required=True, ondelete='cascade')#O2M
    select_to_pay = fields.Boolean('Select', copy=0)
    name = fields.Char(string="Number")
    account_move_id = fields.Many2one('account.move', string='Move', required=True)
    move_currency_id = fields.Many2one(string='Move Currency', related='account_move_id.currency_id', readonly=True)
    invoice_date = fields.Date(string="Date",related='account_move_id.invoice_date')
    ref = fields.Char(string="Reference", related='account_move_id.ref', readonly=True)
    company_id = fields.Many2one('res.company', string='Company',related='account_move_id.company_id',)
    company_currency_id = fields.Many2one(string='Company Currency', related='company_id.currency_id', readonly=True)
    amount_untaxed = fields.Monetary( 
        string='Untaxed Amount',
        related='account_move_id.amount_untaxed', readonly=True,
        currency_field='move_currency_id')
    amount_total = fields.Monetary(
        string='Total Amount',
        related='account_move_id.amount_total', readonly=True,
        currency_field='move_currency_id',
    )
    amount_residual = fields.Monetary(
        string='Amount Due',
        related='account_move_id.amount_residual', readonly=True,
        currency_field='move_currency_id'
    )
    move_state = fields.Selection(
        related='account_move_id.state', string='Estado', readonly=True)
    payment_state = fields.Selection(
        related='account_move_id.payment_state', string='Estado de pago', readonly=True)
    is_payable = fields.Boolean(
        string='Aplicable',
        compute='_compute_is_payable',
        help="Falso cuando el documento ya no tiene saldo pendiente o no está "
             "publicado; en ese caso el pago no puede aplicarse a él.",
    )

    @api.depends('account_move_id.state', 'account_move_id.amount_residual',
                 'account_move_id.currency_id')
    def _compute_is_payable(self):
        for line in self:
            move = line.account_move_id
            rounding = move.currency_id.rounding or 0.01
            line.is_payable = bool(
                move
                and move.state == 'posted'
                and not float_is_zero(move.amount_residual, precision_rounding=rounding)
            )

    @api.depends('name', 'account_move_id.name')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.account_move_id.name or line.name or ''

    def open_invoice(self):
        self.ensure_one()
        name = ''
        if self.account_move_id.move_type == 'out_invoice':
            name = 'Customer Invoice'
        if self.account_move_id.move_type == 'in_invoice':
            name = 'Vendor Bill'
        return {
            'type': 'ir.actions.act_window',
            #'name': _("Customer Invoice"),
            'name': name,
            'view_id': self.env.ref('account.view_move_form').id,
            'context': self.env.context,
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'target': 'new',
            'view_mode': 'form',
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
