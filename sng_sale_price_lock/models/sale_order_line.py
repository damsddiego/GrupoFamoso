from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

FORCE_GROUP = 'sng_sale_price_lock.group_sng_force_price'

# Contexto de escape para flujos automaticos legitimos que deban fijar un
# precio fuera de la lista (migraciones, scripts, modulos propios).
SKIP_CTX = 'sng_skip_price_lock'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sng_price_locked = fields.Boolean(
        string='Precio bloqueado',
        compute='_compute_sng_price_lock_flags',
    )
    sng_discount_locked = fields.Boolean(
        string='Descuento bloqueado',
        compute='_compute_sng_price_lock_flags',
    )

    # ------------------------------------------------------------------
    # Flags (solo UI: el control real esta en create/write)
    # ------------------------------------------------------------------

    @api.depends(
        'company_id', 'order_id.pricelist_id', 'product_id', 'display_type',
        'is_downpayment', 'is_expense', 'qty_invoiced', 'combo_item_id',
    )
    @api.depends_context('uid')
    def _compute_sng_price_lock_flags(self):
        privileged = self.env.user.has_group(FORCE_GROUP)
        for line in self:
            company = line.company_id or line.env.company
            active = not privileged and not line._sng_price_lock_skip()
            line.sng_price_locked = active and company.sng_lock_price_unit
            line.sng_discount_locked = active and company.sng_lock_discount

    # ------------------------------------------------------------------
    # Alcance del bloqueo
    # ------------------------------------------------------------------

    def _sng_price_lock_skip(self):
        """Lineas que nunca se validan: su precio no lo define la lista."""
        self.ensure_one()
        if self.display_type or not self.product_id:
            return True
        if not self.order_id.pricelist_id:
            return True
        if self.is_downpayment or self.is_expense:
            return True
        # Combos: el precio del padre es 0 y el del hijo es una fraccion.
        if self.combo_item_id or self.product_type == 'combo':
            return True
        # Ya facturada: Odoo tampoco recalcula el precio en ese caso.
        if self.qty_invoiced:
            return True
        # Linea de gastos de envio creada por el modulo delivery.
        if 'is_delivery' in self._fields and self.is_delivery:
            return True
        # Linea de recompensa creada por sale_loyalty (cupones, promociones).
        if 'is_reward_line' in self._fields and self.is_reward_line:
            return True
        # Linea de descuento global creada por el asistente nativo de descuentos.
        company = self.company_id or self.env.company
        if self.product_id == company.sudo().sale_discount_product_id:
            return True
        return False

    # ------------------------------------------------------------------
    # Valores esperados segun la lista de precios
    # ------------------------------------------------------------------

    def _sng_expected_price_unit(self):
        """Precio que arrojaria la lista de precios.

        Replica ``_reset_price_unit()`` de ``sale`` sin escribir en el registro.
        """
        self.ensure_one()
        line = self.with_company(self.company_id)
        product_taxes = line.product_id.taxes_id._filter_taxes_by_company(line.company_id)
        return line.product_id._get_tax_included_unit_price_from_price(
            line._get_display_price(),
            product_taxes=product_taxes,
            fiscal_position=line.order_id.fiscal_position_id,
        )

    def _sng_expected_discount(self):
        """Descuento que arrojaria la lista de precios.

        Replica ``_compute_discount()`` de ``sale``. Devuelve 0 cuando la regla
        aplicada no expresa un descuento (o cuando no hubo regla alguna).
        """
        self.ensure_one()
        if not self.env['product.pricelist.item']._is_discount_feature_enabled():
            return 0.0
        if not self.pricelist_item_id._show_discount():
            return 0.0
        line = self.with_company(self.company_id)
        base_price = line._get_pricelist_price_before_discount()
        if not base_price:
            return 0.0
        pricelist_price = line._get_pricelist_price()
        discount = (base_price - pricelist_price) / base_price * 100
        # Los recargos (descuento negativo con precio positivo) no se muestran.
        if (discount > 0 and base_price > 0) or (discount < 0 and base_price < 0):
            return discount
        return 0.0

    # ------------------------------------------------------------------
    # Validacion
    # ------------------------------------------------------------------

    def _sng_check_price_lock(self, fnames):
        if self.env.context.get(SKIP_CTX):
            return
        if self.env.user.has_group(FORCE_GROUP):
            return

        price_digits = self.env['decimal.precision'].precision_get('Product Price')
        discount_digits = self.env['decimal.precision'].precision_get('Discount')

        for line in self:
            company = line.company_id or self.env.company
            if line._sng_price_lock_skip():
                continue

            if 'price_unit' in fnames and company.sng_lock_price_unit:
                expected = line._sng_expected_price_unit()
                if line._sng_value_rejected(
                    line.price_unit, expected, price_digits,
                    company.sng_price_lock_tolerance,
                    allow_above=company.sng_price_lock_mode == 'no_lower',
                    allow_below=False,
                ):
                    raise UserError(line._sng_lock_message(
                        _("precio unitario"), line.price_unit, expected))

            if 'discount' in fnames and company.sng_lock_discount:
                expected = line._sng_expected_discount()
                if line._sng_value_rejected(
                    line.discount, expected, discount_digits,
                    company.sng_price_lock_tolerance,
                    allow_above=False,
                    allow_below=company.sng_discount_lock_mode == 'no_higher',
                ):
                    raise UserError(line._sng_lock_message(
                        _("descuento"), line.discount, expected))

    def _sng_value_rejected(self, actual, expected, digits, tolerance,
                            allow_above, allow_below):
        """True si ``actual`` se aparta de ``expected`` mas de lo permitido."""
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

    def _sng_lock_message(self, label, actual, expected):
        self.ensure_one()
        pricelist = self.order_id.pricelist_id
        if self.pricelist_item_id:
            origen = _(
                "Regla aplicada: %(rule)s (lista %(pricelist)s).",
                rule=self.pricelist_item_id.display_name,
                pricelist=pricelist.display_name,
            )
        else:
            origen = _(
                "La lista de precios %(pricelist)s no tiene ninguna regla para "
                "este producto, por lo que se usa su precio de venta.",
                pricelist=pricelist.display_name,
            )
        return _(
            "No puede modificar el %(label)s del producto %(product)s.\n\n"
            "Valor capturado: %(actual)s\n"
            "Valor segun la lista de precios: %(expected)s\n\n"
            "%(origen)s\n\n"
            "Solicite el cambio a un usuario con el permiso "
            "\"Modificar precio/descuento fuera de la lista de precios\", o "
            "ajuste la lista de precios.",
            label=label,
            product=self.product_id.display_name,
            actual=actual,
            expected=expected,
            origen=origen,
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sng_check_price_lock(('price_unit', 'discount'))
        return lines

    def write(self, vals):
        res = super().write(vals)
        fnames = tuple(f for f in ('price_unit', 'discount') if f in vals)
        if fnames:
            self._sng_check_price_lock(fnames)
        return res
