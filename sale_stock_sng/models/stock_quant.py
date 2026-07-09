# -*- coding: utf-8 -*-
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = "stock.quant"

    in_my_location = fields.Boolean(
        string="En mi bodega",
        compute="_compute_in_my_location",
        search="_search_in_my_location",
        store=False,
    )

    # === Internos ===
    def _get_user_root_location(self):
        """Obtiene la stock.location raíz desde partner.sale_location_id.
           - Si es stock.warehouse -> view_location_id
           - Si es stock.location  -> esa misma
           - Si no hay nada        -> False
        """
        partner = self.env.user.sudo().partner_id
        sale_loc = getattr(partner, "sale_location_id", False)
        if not sale_loc:
            return False
        model = getattr(sale_loc, "_name", "")
        if model == "stock.warehouse":
            return sale_loc.view_location_id or False
        if model == "stock.location":
            return sale_loc
        return False

    def _compute_in_my_location(self):
        root = self._get_user_root_location()
        for q in self:
            if not root or not q.location_id:
                q.in_my_location = False
            else:
                # Marca True si es la misma o hija
                try:
                    is_child = q.location_id._is_child_of(root)
                except Exception:
                    # Fallback para ediciones que no tengan _is_child_of
                    is_child = q.location_id.id in self.env["stock.location"].search(
                        [("id", "child_of", root.id)]
                    ).ids
                q.in_my_location = bool(is_child or q.location_id.id == root.id)

    def _search_in_my_location(self, operator, value):
        """Permite domain [('in_my_location','=',True)] sin referenciar 'user' en XML."""
        root = self._get_user_root_location()
        # Si no hay raíz y piden True -> no resultados
        if not root:
            return [("id", "=", 0)] if (operator in ("=", "==") and bool(value)) else []
        # '=' o '=='
        if operator in ("=", "=="):
            if bool(value):
                # incluir raíz exacta y sus hijas
                return ["|", ("location_id", "=", root.id), ("location_id", "child_of", root.id)]
            else:
                # negación
                return ["!", "|", ("location_id", "=", root.id), ("location_id", "child_of", root.id)]
        # Otros operadores no aplican a booleanos
        return []
