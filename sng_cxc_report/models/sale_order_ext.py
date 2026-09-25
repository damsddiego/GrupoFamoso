# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for order in self:
            # El bloqueo se gestiona a nivel del partner comercial (empresa),
            # pero la orden puede usar un contacto hijo (sucursal/direccion).
            blocked_partner = order.partner_id.commercial_partner_id
            if order.partner_id.sng_credit_blocked or blocked_partner.sng_credit_blocked:
                raise UserError(
                    _(
                        "El cliente '%s' tiene el credito bloqueado por el departamento de CxC. "
                        "Contacte a Jefatura CxC para liberar el bloqueo antes de confirmar esta orden."
                    )
                    % blocked_partner.display_name
                )
        return super().action_confirm()
