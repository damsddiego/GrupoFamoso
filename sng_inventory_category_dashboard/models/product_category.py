# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    inventory_dashboard_target_days = fields.Float(
        string="Cobertura objetivo (dias)",
        default=40.0,
        tracking=True,
        help="Cobertura deseada para la categoria en el dashboard de inventario.",
    )
    inventory_dashboard_buy_threshold = fields.Float(
        string="Umbral comprar (dias)",
        default=20.0,
        tracking=True,
        help="Si los dias de inventario quedan por debajo de este valor, la accion sera COMPRAR.",
    )
    inventory_dashboard_liquidate_threshold = fields.Float(
        string="Umbral liquidar (dias)",
        default=60.0,
        tracking=True,
        help="Si los dias de inventario superan este valor, la accion sera LIQUIDAR.",
    )

    @api.constrains(
        "inventory_dashboard_target_days",
        "inventory_dashboard_buy_threshold",
        "inventory_dashboard_liquidate_threshold",
    )
    def _check_inventory_dashboard_thresholds(self):
        for category in self:
            if category.inventory_dashboard_target_days < 0:
                raise ValidationError(_("La cobertura objetivo no puede ser negativa."))
            if category.inventory_dashboard_buy_threshold < 0:
                raise ValidationError(_("El umbral de compra no puede ser negativo."))
            if category.inventory_dashboard_liquidate_threshold < category.inventory_dashboard_buy_threshold:
                raise ValidationError(
                    _("El umbral de liquidacion debe ser mayor o igual al umbral de compra.")
                )
