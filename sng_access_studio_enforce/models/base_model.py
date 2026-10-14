# -*- coding: utf-8 -*-
"""Gancho genérico: cualquier modelo puede llamar
``self._sng_access_studio_check_method("nombre_metodo")`` al inicio de un
método para rechazar la llamada cuando el usuario actual tiene, en un
perfil activo de Access Studio, una regla de botón con ese nombre marcada
como "Bloquear también en servidor"."""
import logging

from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class BaseSngAccessStudioEnforce(models.AbstractModel):
    _inherit = "base"

    def _sng_access_studio_enforced_nodes(self, method_name):
        """Reglas de botón con enforce_server activas para el usuario
        actual en este modelo y método. Vacío si no aplica."""
        Node = self.env["eh.access.node"].sudo()
        if self.env.su or self.env.uid == SUPERUSER_ID:
            return Node.browse()
        if "eh.access.profile" not in self.env:
            return Node.browse()
        Profile = self.env["eh.access.profile"].sudo()
        profile_ids = Profile._get_active_profile_ids(
            self.env.user.id,
            self.env.company.id,
            Profile._today_for_cache_key(),
        )
        if not profile_ids:
            return Node.browse()
        return Node.search([
            ("profile_id", "in", list(profile_ids)),
            ("model_name", "=", self._name),
            ("kind", "=", "button"),
            ("target_name", "=", method_name),
            ("enforce_server", "=", True),
        ])

    def _sng_access_studio_check_method(self, method_name):
        nodes = self._sng_access_studio_enforced_nodes(method_name)
        if not nodes:
            return
        _logger.info(
            "Access Studio: bloqueado %s.%s para uid %s por perfil(es) %s",
            self._name, method_name, self.env.uid,
            ", ".join(nodes.mapped("profile_id.name")),
        )
        raise AccessError(_(
            "Access Studio: su perfil de acceso (%(profiles)s) no permite"
            " ejecutar '%(label)s' en %(model)s.",
            profiles=", ".join(nodes.mapped("profile_id.name")),
            label=nodes[0].target_label or method_name,
            model=self._description or self._name,
        ))
