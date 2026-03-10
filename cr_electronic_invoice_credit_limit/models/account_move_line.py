from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    remaining_qty_to_refund = fields.Float(
        string='Remaining Qty to Refund',
        compute='_compute_remaining_qty_to_refund',
        store=False,
        help='Quantity that can still be refunded for this product from the original invoice'
    )

    @api.depends('move_id', 'product_id', 'quantity')
    def _compute_remaining_qty_to_refund(self):
        """
        Calculate remaining quantity that can be refunded for each invoice line
        """
        for line in self:
            line.remaining_qty_to_refund = 0.0

            # Only compute for invoice lines (not credit notes)
            if line.move_id.move_type != 'out_invoice' or line.display_type or not line.product_id:
                continue

            # Search for all posted credit notes related to this invoice
            # Only count posted credit notes, not drafts
            credit_notes = self.env['account.move'].search([
                ('reversed_entry_id', '=', line.move_id.id),
                ('state', '=', 'posted'),  # Only posted credit notes
                ('move_type', '=', 'out_refund')
            ])

            # Sum quantities already refunded for this specific product
            refunded_qty = 0.0
            for cn in credit_notes:
                cn_lines = cn.invoice_line_ids.filtered(
                    lambda l: l.product_id == line.product_id and not l.display_type
                )
                refunded_qty += sum(cn_lines.mapped('quantity'))

            # Calculate remaining quantity available to refund
            line.remaining_qty_to_refund = line.quantity - refunded_qty

    @api.constrains('product_id', 'quantity', 'move_id')
    def _check_refund_quantity_limit(self):
        """
        Validate that credit note quantities don't exceed original invoice quantities per product
        """
        for line in self:
            # Only validate credit note lines with products
            if line.move_id.move_type != 'out_refund' or line.display_type or not line.product_id:
                continue

            # Skip validation if credit note is still in draft state
            # This allows users to edit quantities before posting
            if line.move_id.state == 'draft':
                continue

            # Only if there's an original invoice
            if not line.move_id.reversed_entry_id:
                continue

            # Find the original line(s) with the same product
            original_lines = line.move_id.reversed_entry_id.invoice_line_ids.filtered(
                lambda l: l.product_id == line.product_id and not l.display_type
            )

            if not original_lines:
                raise ValidationError(_(
                    'Product "%s" was not found in the original invoice.\n'
                    'You can only refund products that were in the original invoice.'
                ) % line.product_id.display_name)

            # Calculate total quantity in original invoice for this product
            original_qty = sum(original_lines.mapped('quantity'))

            # Calculate total already refunded (excluding current credit note)
            # Only count posted credit notes, exclude drafts and cancelled
            other_refunds = self.env['account.move'].search([
                ('reversed_entry_id', '=', line.move_id.reversed_entry_id.id),
                ('state', 'not in', ['cancel', 'draft']),
                ('move_type', '=', 'out_refund'),
                ('id', '!=', line.move_id.id)
            ])

            total_refunded = 0.0
            for refund in other_refunds:
                refund_lines = refund.invoice_line_ids.filtered(
                    lambda l: l.product_id == line.product_id and not l.display_type
                )
                total_refunded += sum(refund_lines.mapped('quantity'))

            # Calculate available quantity
            available_qty = original_qty - total_refunded

            # Validate quantity limit
            if line.quantity > available_qty:
                raise ValidationError(_(
                    'Cannot refund more than available quantity!\n\n'
                    'Product: %s\n'
                    'Original Invoice: %s\n'
                    'Original Quantity: %.2f %s\n'
                    'Already Refunded: %.2f %s\n'
                    'Available to Refund: %.2f %s\n'
                    'Trying to Refund: %.2f %s\n\n'
                    'Please adjust the quantity to %.2f or less.'
                ) % (
                    line.product_id.display_name,
                    line.move_id.reversed_entry_id.name,
                    original_qty,
                    line.product_uom_id.name or '',
                    total_refunded,
                    line.product_uom_id.name or '',
                    available_qty,
                    line.product_uom_id.name or '',
                    line.quantity,
                    line.product_uom_id.name or '',
                    available_qty
                ))

    @api.constrains('move_id', 'price_subtotal')
    def _check_credit_note_line_limit(self):
        """Additional validation at line level for credit notes"""
        for line in self:
            move = line.move_id
            if move.move_type == 'out_refund' and move.reversed_entry_id:
                # Skip validation if credit note is still in draft state
                if move.state == 'draft':
                    continue

                original_invoice = move.reversed_entry_id
                # Calculate total of all credit notes including this one
                # Only count posted credit notes, exclude drafts and cancelled
                existing_credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', original_invoice.id),
                    ('state', 'not in', ['cancel', 'draft']),
                    ('move_type', '=', 'out_refund'),
                    ('id', '!=', move.id)
                ])
                total_credit_amount = sum(existing_credit_notes.mapped('amount_total')) + move.amount_total
                
                if total_credit_amount > original_invoice.amount_total:
                    raise ValidationError(_(
                        "Adding this line would cause the total credit notes amount (%s) "
                        "to exceed the original invoice amount (%s)."
                    ) % (total_credit_amount, original_invoice.amount_total))