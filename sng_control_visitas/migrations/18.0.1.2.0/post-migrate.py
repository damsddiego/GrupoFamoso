# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, fields

from odoo.addons.sng_control_visitas.hooks import marcar_clientes_genericos

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    marcar_clientes_genericos(env)

    # Regenera el mes actual para que los clientes genéricos, la compañía y
    # los de crédito bloqueado salgan de la matriz sin esperar al cron.
    hoy = fields.Date.today()
    Linea = env['sng.control.visitas.linea']
    for company in env['res.company'].search([]):
        try:
            Linea._sng_generar_mes(hoy, company)
        except Exception:  # noqa: BLE001
            _logger.exception(
                'sng_control_visitas: no se pudo regenerar la matriz de %s',
                company.name)
