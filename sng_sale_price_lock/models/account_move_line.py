from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .sale_order_line import FORCE_GROUP, SKIP_CTX


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    sng_price_locked = fields.Boolean(
        string='Precio bloqueado',
        compute='_compute_sng_invoice_price_lock_flags',
    )
    sng_discount_locked = fields.Boolean(
        string='Descuento bloqueado',
        compute='_compute_sng_invoice_price_lock_flags',
    )

    @api.depends(
        'company_id', 'move_id.move_type', 'move_id.sng_pricelist_id',
        'product_id', 'display_type', 'is_downpayment', 'sale_line_ids',
    )
    @api.depends_context('uid')
    def _compute_sng_invoice_price_lock_flags(self):
        privileged = self.env.user.has_group(FORCE_GROUP)
        for line in self:
            company = line.company_id or line.env.company
            active = not privileged and not line._sng_invoice_price_lock_skip()
            line.sng_price_locked = active and company.sng_lock_price_unit
            line.sng_discount_locked = active and company.sng_lock_discount

    def _sng_source_sale_line_skipped(self, sale_line):
        """Origenes cuyo precio no representa una condicion comercial normal."""
        if sale_line.display_type or not sale_line.product_id:
            return True
        if sale_line.is_downpayment or sale_line.is_expense:
            return True
        if sale_line.combo_item_id or sale_line.product_type == 'combo':
            return True
        if 'is_delivery' in sale_line._fields and sale_line.is_delivery:
            return True
        if 'is_reward_line' in sale_line._fields and sale_line.is_reward_line:
            return True
        company = sale_line.company_id or self.env.company
        return sale_line.product_id == company.sudo().sale_discount_product_id

    def _sng_invoice_price_lock_skip(self):
        self.ensure_one()
        move = self.move_id
        if not move or not move.is_sale_document(include_receipts=True):
            return True
        if self.display_type != 'product' or not self.product_id:
            return True
        if self.is_downpayment:
            return True
        company = self.company_id or self.env.company
        if self.product_id == company.sudo().sale_discount_product_id:
            return True
        source_lines = self.sale_line_ids.filtered(
            lambda sale_line: not self._sng_source_sale_line_skipped(sale_line)
        )
        if self.sale_line_ids:
            return not source_lines
        return not move.sng_pricelist_id

    def _sng_source_sale_line(self):
        self.ensure_one()
        return self.sale_line_ids.filtered(
            lambda sale_line: not self._sng_source_sale_line_skipped(sale_line)
        )[:1]

    def _sng_manual_pricelist_values(self):
        """Precio visible, descuento y regla para una factura manual."""
        self.ensure_one()
        move = self.move_id
        pricelist = move.sng_pricelist_id
        product = self.product_id.with_company(self.company_id)
        quantity = self.quantity or 1.0
        uom = self.product_uom_id or product.uom_id
        date = move.invoice_date or move.date or fields.Date.context_today(self)

        price, rule_id = pricelist._get_product_price_rule(
            product,
            quantity,
            uom=uom,
            date=date,
            currency=move.currency_id,
        )
        rule = self.env['product.pricelist.item'].browse(rule_id)
        discount = 0.0
        display_price = price
        if rule._show_discount():
            base_price = rule._compute_price_before_discount(
                product,
                quantity,
                uom,
                date=date,
                currency=move.currency_id,
            )
            display_price = max(base_price, price)
            if base_price:
                candidate = (base_price - price) / base_price * 100
                if (
                    (candidate > 0 and base_price > 0)
                    or (candidate < 0 and base_price < 0)
                ):
                    discount = candidate

        product_taxes = product.taxes_id._filter_taxes_by_company(self.company_id)
        price_unit = product._get_tax_included_unit_price_from_price(
            display_price,
            product_taxes=product_taxes,
            fiscal_position=move.fiscal_position_id,
        )
        return price_unit, discount, rule

    def _sng_expected_invoice_values(self):
        self.ensure_one()
        source_line = self._sng_source_sale_line()
        if source_line:
            return (
                source_line.price_unit,
                source_line.discount,
                source_line.pricelist_item_id,
                source_line,
            )
        price, discount, rule = self._sng_manual_pricelist_values()
        return price, discount, rule, self.env['sale.order.line']

    def _sng_value_rejected(self, actual, expected, digits, tolerance,
                            allow_above, allow_below):
        if tolerance:
            margin = abs(expected) * tolerance / 100.0
            if abs(actual - expected) <= margin:
                return False
        comparison = float_compare(actual, expected, precision_digits=digits)
        if comparison == 0:
            return False
        if comparison > 0:
            return not allow_above
        return not allow_below

    def _sng_check_invoice_price_lock(self, fnames):
        if self.env.context.get(SKIP_CTX):
            return
        if self.env.user.has_group(FORCE_GROUP):
            return

        price_digits = self.env['decimal.precision'].precision_get('Product Price')
        discount_digits = self.env['decimal.precision'].precision_get('Discount')
        for line in self:
            company = line.company_id or self.env.company
            if line._sng_invoice_price_lock_skip():
                continue
            expected_price, expected_discount, rule, source_line = (
                line._sng_expected_invoice_values()
            )
            if (
                'price_unit' in fnames
                and company.sng_lock_price_unit
                and line._sng_value_rejected(
                    line.price_unit,
                    expected_price,
                    price_digits,
                    company.sng_price_lock_tolerance,
                    allow_above=company.sng_price_lock_mode == 'no_lower',
                    allow_below=False,
                )
            ):
                raise UserError(line._sng_invoice_lock_message(
                    _('precio unitario'), line.price_unit, expected_price,
                    rule, source_line,
                ))
            if (
                'discount' in fnames
                and company.sng_lock_discount
                and line._sng_value_rejected(
                    line.discount,
                    expected_discount,
                    discount_digits,
                    company.sng_price_lock_tolerance,
                    allow_above=False,
                    allow_below=company.sng_discount_lock_mode == 'no_higher',
                )
            ):
                raise UserError(line._sng_invoice_lock_message(
                    _('descuento'), line.discount, expected_discount,
                    rule, source_line,
                ))

    def _sng_invoice_lock_message(self, label, actual, expected, rule, source_line):
        self.ensure_one()
        if source_line:
            origin = _(
                'La linea proviene del pedido %(order)s.',
                order=source_line.order_id.display_name,
            )
        elif rule:
            origin = _(
                'Regla aplicada: %(rule)s (lista %(pricelist)s).',
                rule=rule.display_name,
                pricelist=self.move_id.sng_pricelist_id.display_name,
            )
        else:
            origin = _(
                'La lista %(pricelist)s no tiene una regla especifica; se usa '
                'el precio de venta del producto.',
                pricelist=self.move_id.sng_pricelist_id.display_name,
            )
        return _(
            'No puede modificar el %(label)s del producto %(product)s en la '
            'factura.\n\nValor capturado: %(actual)s\nValor permitido: '
            '%(expected)s\n\n%(origin)s\n\nSolicite el cambio a un usuario '
            'con el permiso "Modificar precio/descuento fuera de la lista de '
            'precios", o ajuste la lista de precios.',
            label=label,
            product=self.product_id.display_name,
            actual=actual,
            expected=expected,
            origin=origin,
        )

    def _sng_reset_invoice_locked_values(self, field_names=None):
        if self.env.context.get(SKIP_CTX) or self.env.user.has_group(FORCE_GROUP):
            return
        requested = set(field_names or ('price_unit', 'discount'))
        for line in self:
            if line._sng_invoice_price_lock_skip():
                continue
            company = line.company_id or self.env.company
            expected_price, expected_discount, _rule, _source = (
                line._sng_expected_invoice_values()
            )
            vals = {}
            if 'price_unit' in requested and company.sng_lock_price_unit:
                vals['price_unit'] = expected_price
            if 'discount' in requested and company.sng_lock_discount:
                vals['discount'] = expected_discount
            if vals:
                line.with_context(**{SKIP_CTX: True}).update(vals)

    @api.onchange(
        'product_id', 'product_uom_id', 'quantity', 'move_id.sng_pricelist_id',
        'move_id.invoice_date', 'move_id.date', 'move_id.currency_id',
        'move_id.fiscal_position_id',
    )
    def _onchange_sng_invoice_locked_values(self):
        self._sng_reset_invoice_locked_values()

    @api.model_create_multi
    def create(self, vals_list):
        supplied = [set(vals) for vals in vals_list]
        lines = super().create(vals_list)
        for line, field_names in zip(lines, supplied):
            missing = {'price_unit', 'discount'} - field_names
            line._sng_reset_invoice_locked_values(missing)
        lines._sng_check_invoice_price_lock(('price_unit', 'discount'))
        return lines

    def write(self, vals):
        res = super().write(vals)
        basis_fields = {
            'product_id', 'product_uom_id', 'quantity', 'sale_line_ids',
            'move_id',
        }
        fields_to_check = set(vals).intersection({'price_unit', 'discount'})
        if basis_fields.intersection(vals):
            missing = {'price_unit', 'discount'} - set(vals)
            self._sng_reset_invoice_locked_values(missing)
            fields_to_check.update(('price_unit', 'discount'))
        if fields_to_check:
            self._sng_check_invoice_price_lock(tuple(fields_to_check))
        return res
