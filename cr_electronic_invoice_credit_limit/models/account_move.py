from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Add a computed field to track credit note totals
    credit_note_total = fields.Monetary(
        string='Total Credit Notes',
        compute='_compute_credit_note_total',
        store=True,
        help='Total amount of credit notes created for this invoice'
    )

    # Fields for stock return management
    return_location_id = fields.Many2one(
        'stock.location',
        string='Return Location',
        domain="[('usage', '=', 'internal')]",
        help='Location where returned products will be stored. If empty, products will not be returned to inventory.'
    )

    has_stock_delivery = fields.Boolean(
        string='Has Stock Delivery',
        compute='_compute_has_stock_delivery',
        store=False,
        help='Indicates if this invoice comes from a sale order with a completed delivery'
    )

    return_location_required = fields.Boolean(
        string='Return Location Required',
        compute='_compute_return_location_required',
        store=False,
        help='Indicates if return location is mandatory for this credit note'
    )

    stock_return_picking_id = fields.Many2one(
        'stock.picking',
        string='Return Picking',
        readonly=True,
        help='Stock picking generated for this credit note return'
    )

    @api.depends('reversed_entry_id', 'reversed_entry_id.invoice_line_ids.sale_line_ids.order_id.picking_ids')
    def _compute_has_stock_delivery(self):
        """Check if the invoice (or reversed invoice for credit notes) has a completed stock delivery"""
        for move in self:
            move.has_stock_delivery = False

            # For credit notes, check the original invoice
            invoice_to_check = move.reversed_entry_id if move.move_type == 'out_refund' else move

            if not invoice_to_check:
                continue

            # Get sale orders from invoice lines
            sale_orders = invoice_to_check.invoice_line_ids.mapped('sale_line_ids.order_id')

            if sale_orders:
                # Check if there are completed deliveries (outgoing pickings in done state)
                completed_deliveries = sale_orders.mapped('picking_ids').filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                )
                move.has_stock_delivery = bool(completed_deliveries)

    @api.depends('move_type', 'has_stock_delivery')
    def _compute_return_location_required(self):
        """Determine if return location is required for this credit note"""
        for move in self:
            # Return location is required only for credit notes with stock delivery
            move.return_location_required = (
                move.move_type == 'out_refund' and move.has_stock_delivery
            )

    @api.depends('reversed_entry_id', 'reversed_entry_id.line_ids', 'state')
    def _compute_credit_note_total(self):
        """Compute the total amount of credit notes for an invoice"""
        for move in self:
            if move.move_type == 'out_refund' and move.reversed_entry_id:
                # Find all credit notes linked to the original invoice
                credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', move.reversed_entry_id.id),
                    ('state', 'not in', ['cancel', 'draft']),
                    ('move_type', '=', 'out_refund')
                ])
                move.credit_note_total = sum(credit_notes.mapped('amount_total'))
            else:
                move.credit_note_total = 0.0

    def _post(self, soft=True):
        """Override to create stock return when credit note is posted"""
        # Call parent method first
        res = super(AccountMove, self)._post(soft=soft)

        # Create stock return for credit notes with return location
        for move in self:
            _logger.info("=== CREDIT NOTE POST DEBUG ===")
            _logger.info(f"Move: {move.name}, Type: {move.move_type}")
            _logger.info(f"Return Location: {move.return_location_id}")
            _logger.info(f"Has Stock Delivery: {move.has_stock_delivery}")
            _logger.info(f"Stock Return Picking: {move.stock_return_picking_id}")

            if (move.move_type == 'out_refund' and
                move.return_location_id and
                move.has_stock_delivery and
                not move.stock_return_picking_id):
                _logger.info(">>> Creating stock return...")
                move._create_stock_return()
            else:
                _logger.info(">>> Conditions not met for stock return")

        return res

    def action_view_stock_return(self):
        """Open the stock return picking"""
        self.ensure_one()
        return {
            'name': _('Stock Return'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.stock_return_picking_id.id,
            'target': 'current',
        }

    def action_debug_stock_return(self):
        """Debug method to check why stock return is not being created"""
        self.ensure_one()
        msg = []

        msg.append(f"=== DEBUGGING CREDIT NOTE {self.name} ===\n")
        msg.append(f"Move Type: {self.move_type}")
        msg.append(f"Return Location: {self.return_location_id.display_name if self.return_location_id else 'NOT SET'}")
        msg.append(f"Has Stock Delivery: {self.has_stock_delivery}\n")

        if not self.reversed_entry_id:
            msg.append("ERROR: No reversed_entry_id (original invoice)")
            raise ValidationError('\n'.join(msg))

        msg.append(f"Original Invoice: {self.reversed_entry_id.name}")
        msg.append(f"Original Invoice Lines: {len(self.reversed_entry_id.invoice_line_ids)}\n")

        sale_orders = self.reversed_entry_id.invoice_line_ids.mapped('sale_line_ids.order_id')
        msg.append(f"Sale Orders Found: {len(sale_orders)}")
        for so in sale_orders:
            msg.append(f"  - {so.name}")
            pickings = so.picking_ids
            msg.append(f"    Pickings: {len(pickings)}")
            for pick in pickings:
                msg.append(f"      - {pick.name}: type={pick.picking_type_code}, state={pick.state}")

        if not sale_orders:
            msg.append("\nERROR: No sale orders found!")
            raise ValidationError('\n'.join(msg))

        all_pickings = sale_orders.mapped('picking_ids')
        outgoing_done = all_pickings.filtered(lambda p: p.picking_type_code == 'outgoing' and p.state == 'done')
        msg.append(f"\nOutgoing Done Pickings: {len(outgoing_done)}")

        if not outgoing_done:
            msg.append("ERROR: No completed outgoing pickings!")
            raise ValidationError('\n'.join(msg))

        msg.append(f"\nCredit Note Lines: {len(self.invoice_line_ids)}")
        msg.append(f"ALL Lines (including display types):")
        for line in self.invoice_line_ids:
            msg.append(f"  - Name: {line.name}")
            msg.append(f"    Display Type: {line.display_type}")
            msg.append(f"    Product: {line.product_id.name if line.product_id else 'NONE'}")
            msg.append(f"    Product Type: {line.product_id.type if line.product_id else 'N/A'}")
            msg.append(f"    Quantity: {line.quantity}")
            msg.append("")

        msg.append(f"\nLines with Products (filtered):")
        lines_with_products = self.invoice_line_ids.filtered(lambda l: not l.display_type and l.product_id)
        msg.append(f"Count: {len(lines_with_products)}")

        for line in lines_with_products:
            product = line.product_id
            msg.append(f"  - {product.name} (Type: {product.type}, Qty: {line.quantity})")

            if product.type != 'product':
                msg.append(f"    SKIP: Not storable")
                continue

            delivered = outgoing_done.mapped('move_ids').filtered(
                lambda m: m.product_id == product and m.state == 'done'
            )
            msg.append(f"    Delivered moves: {len(delivered)}")
            for dm in delivered:
                msg.append(f"      - {dm.product_id.name}: {dm.product_uom_qty} {dm.product_uom.name}")

            if not delivered:
                msg.append(f"    ERROR: No delivered moves found!")

        raise ValidationError('\n'.join(msg))

    def _create_stock_return(self):
        """Create a stock return picking for the credit note"""
        self.ensure_one()

        _logger.info("=== _create_stock_return START ===")

        if not self.return_location_id:
            _logger.warning("No return location set")
            return

        # Get the original invoice
        original_invoice = self.reversed_entry_id
        _logger.info(f"Original invoice: {original_invoice}")
        if not original_invoice:
            _logger.warning("No reversed_entry_id found")
            return

        # Get sale orders from the original invoice
        sale_orders = original_invoice.invoice_line_ids.mapped('sale_line_ids.order_id')
        _logger.info(f"Sale orders found: {sale_orders}")
        if not sale_orders:
            _logger.warning("No sale orders found from invoice lines")
            return

        # Get completed outgoing pickings
        all_pickings = sale_orders.mapped('picking_ids')
        _logger.info(f"All pickings: {all_pickings}")
        outgoing_pickings = all_pickings.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
        )
        _logger.info(f"Completed outgoing pickings: {outgoing_pickings}")

        if not outgoing_pickings:
            _logger.warning("No completed outgoing pickings found")
            return

        # Get the customer location (where products were delivered)
        customer_location = self.env.ref('stock.stock_location_customers')

        # Get or create incoming picking type
        warehouse = self.return_location_id.warehouse_id
        if not warehouse:
            # Find warehouse that contains this location
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', 'parent_of', self.return_location_id.id)
            ], limit=1)

        if not warehouse:
            raise ValidationError(_(
                "No warehouse found for the selected return location. "
                "Please select a location that belongs to a warehouse."
            ))

        picking_type = warehouse.in_type_id

        # Create stock moves for each product in the credit note
        move_lines = []
        # Filter lines: exclude section/note headers, only include lines with products
        invoice_lines_with_products = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.product_id
        )
        _logger.info(f"Invoice lines with products: {invoice_lines_with_products}")

        for invoice_line in invoice_lines_with_products:
            product = invoice_line.product_id
            _logger.info(f"Processing product: {product.name}, Type: {product.type}")

            # Skip services - they don't have physical stock to return
            if product.type == 'service':
                _logger.info(f"Skipping {product.name} - service product (no physical return)")
                continue

            # For storable products (type='product'), verify they were actually delivered
            # For consumables (type='consu'), we can still create returns even without stock moves
            if product.type == 'product':
                # Check if this product was actually delivered
                delivered_moves = outgoing_pickings.mapped('move_ids').filtered(
                    lambda m: m.product_id == product and m.state == 'done'
                )
                _logger.info(f"Delivered moves for {product.name}: {delivered_moves}")

                if not delivered_moves:
                    _logger.warning(f"Storable product {product.name} was not delivered - skipping")
                    continue
            else:
                # Consumable product - create return without checking stock moves
                _logger.info(f"Processing consumable: {product.name} (no stock move validation)")

            # Create the return move
            move_vals = {
                'name': _('Return: %s') % product.display_name,
                'product_id': product.id,
                'product_uom_qty': invoice_line.quantity,
                'product_uom': invoice_line.product_uom_id.id,
                'location_id': customer_location.id,
                'location_dest_id': self.return_location_id.id,
                'picking_type_id': picking_type.id,
            }
            _logger.info(f"Adding move for {product.name}: qty={invoice_line.quantity}")
            move_lines.append((0, 0, move_vals))

        # Only create picking if there are moves
        _logger.info(f"Total move lines to create: {len(move_lines)}")
        if move_lines:
            # Create the picking first (empty) with clean context
            picking_vals = {
                'picking_type_id': picking_type.id,
                'partner_id': self.partner_id.id,
                'origin': self.name,
                'location_id': customer_location.id,
                'location_dest_id': self.return_location_id.id,
            }
            _logger.info(f"Creating picking with vals: {picking_vals}")

            # Create picking in a clean environment without context pollution
            StockPicking = self.env['stock.picking'].sudo()
            picking = StockPicking.create(picking_vals)
            _logger.info(f"Picking created: {picking.name} (ID: {picking.id})")

            # Now create the stock moves and link them to the picking
            for move_cmd in move_lines:
                move_vals = move_cmd[2]  # Extract vals from (0, 0, vals)
                move_vals['picking_id'] = picking.id
                self.env['stock.move'].sudo().create(move_vals)

            # Link the picking to the credit note
            self.stock_return_picking_id = picking.id

            # Confirm the picking automatically
            picking.action_confirm()
            _logger.info(f"Picking {picking.name} confirmed")

            # Optionally auto-validate the picking
            # Uncomment the following lines if you want automatic validation
            # picking.action_assign()
            # for move in picking.move_ids:
            #     move.quantity = move.product_uom_qty
            # picking.button_validate()
        else:
            _logger.warning("No move lines created - picking not generated")

        _logger.info("=== _create_stock_return END ===")

    @api.constrains('return_location_id', 'move_type', 'state', 'has_stock_delivery')
    def _check_return_location_required(self):
        """Ensure return location is set for credit notes with stock delivery"""
        for move in self:
            # Only validate when posting (state changes from draft to posted)
            if (move.move_type == 'out_refund' and
                move.has_stock_delivery and
                move.state == 'posted' and
                not move.return_location_id):
                raise ValidationError(_(
                    "Return Warehouse is required!\n\n"
                    "This credit note is linked to an invoice with a completed delivery.\n"
                    "You must select a warehouse location to return the products.\n\n"
                    "Please select a Return Warehouse before confirming this credit note."
                ))

    @api.constrains('move_type', 'reversed_entry_id', 'amount_total', 'state')
    def _check_credit_note_limit(self):
        """Ensure credit note total doesn't exceed original invoice amount"""
        for move in self:
            # Only check for out_refund (credit notes) that are linked to an original invoice
            # and are not in cancel state
            if (move.move_type == 'out_refund' and move.reversed_entry_id and 
                move.state not in ['cancel', 'draft']):
                original_invoice = move.reversed_entry_id
                # Skip the check if original invoice is cancelled
                if original_invoice.state == 'cancel':
                    continue
                    
                # Calculate total of all credit notes including this one
                # Exclude draft and cancelled credit notes
                existing_credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', original_invoice.id),
                    ('state', 'not in', ['cancel', 'draft']),
                    ('move_type', '=', 'out_refund'),
                    ('id', '!=', move.id)
                ])
                total_credit_amount = sum(existing_credit_notes.mapped('amount_total')) + move.amount_total
                
                # Allow a small tolerance for rounding differences
                if total_credit_amount > (original_invoice.amount_total + 0.01):
                    raise ValidationError(_(
                        "The total amount of credit notes (%.2f) cannot exceed "
                        "the original invoice amount (%.2f).\n"
                        "Original Invoice: %s\n"
                        "Current Credit Notes Total: %.2f\n"
                        "This Credit Note Amount: %.2f"
                    ) % (
                        total_credit_amount,
                        original_invoice.amount_total,
                        original_invoice.name,
                        sum(existing_credit_notes.mapped('amount_total')),
                        move.amount_total
                    ))