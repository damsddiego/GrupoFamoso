# -*- coding: utf-8 -*-
"""Resolución de los IDs de vendedor que manda la app app_ruteros.

Un "vendedor" (rutero) es un CONTACTO marcado con `is_salesperson`, como lo
define sales_commission_omax, no un `res.users`. La app manda el ID de ese
contacto, y a veces ese ID viene de otro entorno y no existe en esta base.
Este helper centraliza la resolución para que la usen tanto los recibos
(account.payment) como las visitas (sng.ruteros.visita).
"""
import json
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

SNG_PARAM_EQUIVALENCIAS = 'sng_ruteros_pagos.vendedor_equivalencias'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _sng_resolver_vendedor_app(self, id_app):
        """Resuelve contra esta base el ID de vendedor que mandó la app.

        Devuelve `(id_resuelto_o_False, aviso_o_None)`:
        - el contacto existe: `(id_app, None)`, sin ruido.
        - no existe pero hay equivalencia configurada en el parámetro de
          sistema `sng_ruteros_pagos.vendedor_equivalencias`
          (JSON `{"id_app": id_real}`): `(id_real, aviso)`.
        - no existe y no hay equivalencia: `(False, aviso)`. El registro entra
          sin vendedor en lugar de reventar por FK y dejar a la app en un
          ciclo de reintentos.
        """
        if not id_app:
            return False, None
        Partner = self.env['res.partner']
        if Partner.browse(id_app).exists():
            return id_app, None

        mapa = {}
        try:
            mapa = json.loads(self.env['ir.config_parameter'].sudo().get_param(
                SNG_PARAM_EQUIVALENCIAS) or '{}')
        except ValueError:
            _logger.warning(
                'Ruteros: el parámetro vendedor_equivalencias no es JSON válido')
        equivalente = mapa.get(str(id_app))
        partner_eq = (Partner.browse(int(equivalente)).exists()
                      if equivalente else Partner)
        if partner_eq:
            _logger.info(
                'Ruteros: vendedor inexistente %s sustituido por %s (%s)',
                id_app, partner_eq.id, partner_eq.name)
            return partner_eq.id, _(
                'La app mandó el vendedor %(orig)s, que no existe en esta '
                'base; se asignó su equivalencia configurada: %(nuevo)s.',
                orig=id_app, nuevo=partner_eq.display_name)

        _logger.warning(
            'Ruteros: vendedor inexistente %s sin equivalencia; el registro '
            'entra sin vendedor', id_app)
        return False, _(
            'La app mandó el vendedor %(orig)s, que no existe en esta base y '
            'no tiene equivalencia configurada. El registro entró SIN '
            'vendedor: asígnelo manualmente y agregue la equivalencia en el '
            'parámetro de sistema "%(param)s".',
            orig=id_app, param=SNG_PARAM_EQUIVALENCIAS)
