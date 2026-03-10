from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, vals):
        if vals.get('state') == 'sale' and not self.env.context.get('skip_stock_block'):
            for order in self:
                message = order._stock_confirmation_error_message()
                if message:
                    raise UserError(message)
        return super().write(vals)

    def _action_confirm(self):
        self._check_stock_before_confirm()
        return super()._action_confirm()

    def _confirmation_error_message(self):
        error = super()._confirmation_error_message()
        if error:
            return error
        return self._stock_confirmation_error_message()

    def _check_stock_before_confirm(self):
        for order in self:
            message = order._stock_confirmation_error_message()
            if message:
                raise UserError(message)

    def _stock_confirmation_error_message(self):
        self.ensure_one()
        company = self.company_id
        if not company.block_sale_without_stock:
            return False
        if company.stock_block_allow_exception_group and self.env.user.has_group(
            'sng_control_sale.group_allow_negative_stock'
        ):
            return False
        if company.stock_block_warehouse_ids and self.warehouse_id not in company.stock_block_warehouse_ids:
            return False

        required_by_product = {}
        for line in self.order_line:
            product = line.product_id
            if not product or line.product_uom_qty <= 0.0:
                continue
            # Odoo 18: use is_storable instead of type == 'product'
            if not product.is_storable:
                continue
            qty = line.product_uom._compute_quantity(
                line.product_uom_qty,
                product.uom_id,
            )
            if qty <= 0.0:
                continue
            required_by_product[product.id] = required_by_product.get(product.id, 0.0) + qty

        if not required_by_product:
            return False

        products = self.env['product.product'].browse(list(required_by_product))
        products = products.with_company(company).with_context(warehouse=self.warehouse_id.id)
        available_by_product = {product.id: product.qty_available for product in products}

        insufficient = []
        for product in products:
            required_qty = required_by_product.get(product.id, 0.0)
            available_qty = available_by_product.get(product.id, 0.0)
            if float_compare(
                required_qty,
                available_qty,
                precision_rounding=product.uom_id.rounding,
            ) > 0:
                insufficient.append((product, required_qty, available_qty))

        if not insufficient:
            return False

        message_lines = [
            _('No hay stock suficiente para confirmar la orden:'),
        ]
        for product, required_qty, available_qty in insufficient:
            message_lines.extend([
                _('Producto: %s') % product.display_name,
                _('Solicitado: %s %s') % (required_qty, product.uom_id.display_name),
                _('Disponible en Almacén %s: %s %s') % (
                    self.warehouse_id.display_name,
                    available_qty,
                    product.uom_id.display_name,
                ),
                '',
            ])
        return '\n'.join(message_lines).strip()

    @api.constrains('state', 'order_line', 'warehouse_id', 'company_id')
    def _check_stock_on_state_sale(self):
        for order in self:
            if order.state != 'sale':
                continue
            message = order._stock_confirmation_error_message()
            if message:
                raise ValidationError(message)
