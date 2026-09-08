# -*- coding: utf-8 -*-
"""Sanea contactos obsoletos enviados por la app antes de guardar ventas."""

import logging

from odoo import api, models
from odoo.addons.sng_ruteros_pagos.models.res_partner import (
    SNG_PARAM_CLIENTES,
)

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _sng_sanear_contactos_app(self, vals_list):
        """Reemplaza IDs de cliente obsoletos por equivalencias vigentes.

        La app puede conservar el ID interno de un contacto que posteriormente
        fue eliminado o fusionado en Odoo. El saneo debe ocurrir antes de
        ``super().create()``/``write()``, porque los cálculos nativos de la
        orden leen el cliente y lanzarían ``MissingError`` antes del INSERT.
        """
        Partner = self.env['res.partner']
        campos = (
            'partner_id',
            'partner_invoice_id',
            'partner_shipping_id',
        )
        for vals in vals_list:
            for campo in campos:
                original = vals.get(campo)
                if not original:
                    continue
                # En órdenes solo se aplican equivalencias configuradas de
                # forma explícita. No se deduce por nombre/auditoría porque
                # una reasignación incorrecta tendría efectos comerciales.
                equivalente = Partner._sng_equivalencia_configurada(
                    original, SNG_PARAM_CLIENTES,
                )
                if not equivalente:
                    continue
                vals[campo] = equivalente.id
                _logger.info(
                    'Ruteros: orden de venta redirige %s de res.partner(%s) '
                    'a res.partner(%s)',
                    campo, original, equivalente.id,
                )

    @api.model_create_multi
    def create(self, vals_list):
        self._sng_sanear_contactos_app(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._sng_sanear_contactos_app([vals])
        return super().write(vals)
