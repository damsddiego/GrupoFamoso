# -*- coding: utf-8 -*-
"""Regla global: solo un administrador (Ajustes) puede archivar clientes.

No depende de perfiles de Access Studio: aplica a todos los usuarios.
Todo camino de archivado (botón Archivar, toggle_active, importación,
API) termina en write({'active': False}), así que la puerta va ahí.
sudo() la salta, igual que _sng_access_studio_check_method."""
import logging

from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        if "active" in vals and not vals["active"]:
            self._sng_check_archive_customer()
        return super().write(vals)

    def _sng_check_archive_customer(self):
        if self.env.su or self.env.uid == SUPERUSER_ID:
            return
        if self.env.user.has_group("base.group_system"):
            return
        customers = self.filtered(
            lambda p: p.active and (
                p.customer_rank > 0
                or p.commercial_partner_id.customer_rank > 0
            )
        )
        if not customers:
            return
        _logger.info(
            "Access Studio: uid %s intentó archivar clientes %s",
            self.env.uid, customers.ids,
        )
        raise AccessError(_(
            "Solo un administrador puede archivar clientes (%(names)s).",
            names=", ".join(customers[:5].mapped("display_name")),
        ))
