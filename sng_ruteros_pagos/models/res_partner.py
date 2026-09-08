# -*- coding: utf-8 -*-
"""Resolución de los IDs de contacto que manda la app app_ruteros.

Un "vendedor" (rutero) es un CONTACTO marcado con `is_salesperson`, como lo
define sales_commission_omax, no un `res.users`. La app manda el ID de ese
contacto, y a veces ese ID viene de otro entorno o de un contacto que ya se
fusionó o se borró en esta base. Lo mismo pasa con el CLIENTE de la visita o
del recibo. Este helper centraliza ambas resoluciones para que las usen los
recibos (account.payment) y las visitas (sng.ruteros.visita).
"""
import json
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

SNG_PARAM_EQUIVALENCIAS = 'sng_ruteros_pagos.vendedor_equivalencias'
SNG_PARAM_CLIENTES = 'sng_ruteros_pagos.cliente_equivalencias'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _sng_leer_equivalencias(self, parametro):
        """Mapa `{"id_app": id_real}` guardado en un parámetro de sistema."""
        try:
            return json.loads(self.env['ir.config_parameter'].sudo().get_param(
                parametro) or '{}')
        except ValueError:
            _logger.warning(
                'Ruteros: el parámetro %s no es JSON válido', parametro)
            return {}

    @api.model
    def _sng_equivalencia_configurada(self, id_app, parametro):
        """Contacto vigente asignado a mano a un ID de app, o vacío."""
        equivalente = self._sng_leer_equivalencias(parametro).get(str(id_app))
        if not equivalente:
            return self.browse()
        return self.browse(int(equivalente)).exists()

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

        partner_eq = Partner._sng_equivalencia_configurada(
            id_app, SNG_PARAM_EQUIVALENCIAS)
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

    @api.model
    def _sng_partner_fusionado(self, partner_id, max_saltos=5):
        """Destino de un cliente eliminado por el asistente de FUSIÓN.

        El asistente de fusionar contactos deja en el chatter del destino un
        mensaje "Se fusionó con los siguientes contactos: ... (ID x)"; se
        sigue ese rastro (encadenado, por si el destino se volvió a
        fusionar). Devuelve el id vigente o None.
        """
        Partner = self.env['res.partner'].sudo()
        actual = partner_id
        for _salto in range(max_saltos):
            self.env.cr.execute("""
                SELECT res_id FROM mail_message
                WHERE model = 'res.partner' AND body LIKE %s
                ORDER BY id DESC LIMIT 1
            """, ('%%(ID {})%%'.format(int(actual)),))
            fila = self.env.cr.fetchone()
            if not fila:
                return None
            actual = fila[0]
            if Partner.browse(actual).exists():
                return actual
        return None

    @api.model
    def _sng_partner_borrado(self, partner_id):
        """Contacto vigente equivalente a uno BORRADO, según la auditoría.

        sng_audit_log guarda una foto del contacto al eliminarlo. Se busca el
        contacto vigente por cédula (`vat`) y, si no hay, por nombre exacto;
        solo se acepta cuando hay UNA sola coincidencia, para no adivinar.
        Devuelve el id vigente o None.
        """
        if 'sng.audit.log' not in self.env:
            return None  # la auditoría no está instalada en esta base
        registro = self.env['sng.audit.log'].sudo().search([
            ('model_name', '=', 'res.partner'),
            ('res_id', '=', partner_id),
            ('action', '=', 'unlink'),
        ], order='id desc', limit=1)
        if not registro:
            return None
        try:
            datos = json.loads(registro.old_values or '{}')
        except ValueError:
            datos = {}
        Partner = self.env['res.partner'].sudo()
        candidatos_por = (
            ('vat', datos.get('vat')),
            ('name', datos.get('name') or registro.record_name),
        )
        for campo, valor in candidatos_por:
            if not valor:
                continue
            candidatos = Partner.search(
                [(campo, '=', valor), ('id', '!=', partner_id)], limit=2)
            if len(candidatos) == 1:
                return candidatos.id
        return None

    @api.model
    def _sng_resolver_cliente_app(self, id_app):
        """Resuelve contra esta base el ID de cliente que mandó la app.

        La app trabaja con su copia local de la cartera, así que sigue
        mandando contactos que aquí ya se fusionaron o se borraron. Sin esta
        resolución el INSERT viola la FK, la app no recibe respuesta y
        reintenta el mismo registro sin fin (el registro se pierde y el log
        se llena).

        Devuelve `(id_resuelto_o_False, aviso_o_None)`, en este orden:
        1. el contacto existe: `(id_app, None)`, sin ruido.
        2. equivalencia puesta a mano en el parámetro de sistema
           `sng_ruteros_pagos.cliente_equivalencias` (manda sobre lo que se
           pueda deducir).
        3. fue fusionado con otro contacto: se sigue el rastro del chatter.
        4. fue borrado: se busca el equivalente por cédula/nombre en la
           bitácora de auditoría.
        5. sin resolver: `(False, aviso)`; queda a cargo de quien llama
           decidir si hay otra fuente (factura, orden, pago) o si el registro
           entra sin cliente.
        """
        if not id_app:
            return False, None
        Partner = self.env['res.partner']
        if Partner.browse(id_app).exists():
            return id_app, None

        partner_eq = Partner._sng_equivalencia_configurada(
            id_app, SNG_PARAM_CLIENTES)
        if partner_eq:
            _logger.info(
                'Ruteros: cliente inexistente %s sustituido por su '
                'equivalencia configurada %s (%s)',
                id_app, partner_eq.id, partner_eq.name)
            return partner_eq.id, _(
                'La app mandó el cliente %(orig)s, que no existe en esta '
                'base; se asignó su equivalencia configurada: %(nuevo)s.',
                orig=id_app, nuevo=partner_eq.display_name)

        fusionado = Partner._sng_partner_fusionado(id_app)
        if fusionado:
            destino = Partner.browse(fusionado)
            _logger.info(
                'Ruteros: cliente %s fue fusionado; sustituido por %s (%s)',
                id_app, fusionado, destino.display_name)
            return fusionado, _(
                'La app mandó el cliente %(orig)s, que fue fusionado con otro '
                'contacto; se asignó %(nuevo)s. Conviene actualizar los datos '
                'en la app.',
                orig=id_app, nuevo=destino.display_name)

        borrado = Partner._sng_partner_borrado(id_app)
        if borrado:
            destino = Partner.browse(borrado)
            _logger.info(
                'Ruteros: cliente %s fue borrado; sustituido por %s (%s) '
                'según la bitácora de auditoría',
                id_app, borrado, destino.display_name)
            return borrado, _(
                'La app mandó el cliente %(orig)s, que fue eliminado de esta '
                'base; según la bitácora de auditoría corresponde a '
                '%(nuevo)s, que es el que se asignó. Conviene actualizar los '
                'datos en la app.',
                orig=id_app, nuevo=destino.display_name)

        _logger.warning(
            'Ruteros: cliente inexistente %s sin fusión ni rastro en la '
            'auditoría', id_app)
        return False, _(
            'La app mandó el cliente %(orig)s, que no existe en esta base: no '
            'aparece fusionado ni en la bitácora de auditoría, y no tiene '
            'equivalencia configurada. Asigne el cliente a mano y agregue la '
            'equivalencia en el parámetro de sistema "%(param)s".',
            orig=id_app, param=SNG_PARAM_CLIENTES)
