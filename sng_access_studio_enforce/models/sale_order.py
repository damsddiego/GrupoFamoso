# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        # Rechazo temprano con mensaje claro. Otros módulos (p. ej. el de
        # límite de crédito) pueden devolver un wizard antes de llamar a
        # super, así que esto no es la garantía: la da _action_confirm.
        self._sng_access_studio_check_method("action_confirm")
        return super().action_confirm()

    def _action_confirm(self):
        # Puerta dura: todo camino que cambie la orden a 'sale' pasa por
        # aquí (action_confirm de sale y de cualquier módulo que lo
        # sobreescriba, wizard de crédito incluido). sudo() la salta.
        self._sng_access_studio_check_method("action_confirm")
        return super()._action_confirm()
