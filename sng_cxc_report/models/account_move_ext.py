# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for move in self:
            # Solo se bloquea la facturacion al cliente (factura/recibo).
            # Las notas de credito reducen la deuda, asi que se permiten
            # aunque el cliente tenga el credito bloqueado.
            if move.move_type in ("out_invoice", "out_receipt"):
                if move.partner_id.sng_credit_blocked or move.commercial_partner_id.sng_credit_blocked:
                    raise UserError(
                        _(
                            "El cliente '%s' tiene el credito bloqueado por el departamento de CxC. "
                            "Contacte a Jefatura CxC para liberar el bloqueo antes de facturar."
                        )
                        % move.commercial_partner_id.display_name
                    )
        return super()._post(soft=soft)
