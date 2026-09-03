"""Asistente para autorizar la reimpresion de un ticket de bodega."""
import json
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

GRUPO = 'sng_reimpresion_ticket.group_reimpresion_ticket'


class SngReimpresionWizard(models.TransientModel):
    _name = 'sng.reimpresion.wizard'
    _description = 'Autorizar la reimpresion de un ticket de bodega'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Orden',
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(related='order_id.partner_id', string='Cliente')
    motivo = fields.Text(
        string='Motivo',
        required=True,
        help='Sale impreso en el ticket y queda en la bitacora. Escriba algo '
             'que le sirva a quien lea el ticket en bodega.',
    )

    copias_previas = fields.Integer(string='Copias ya impresas', readonly=True)
    consulta_ok = fields.Boolean(readonly=True)
    consulta_error = fields.Char(readonly=True)

    entrega_despachada = fields.Boolean(readonly=True)
    entrega_detalle = fields.Char(string='Entregas', readonly=True)

    @api.model
    def default_get(self, fields_list):
        valores = super().default_get(fields_list)
        order_id = valores.get('order_id') or self.env.context.get('active_id')
        if not order_id:
            return valores
        orden = self.env['sale.order'].browse(order_id)
        valores['order_id'] = orden.id

        despachada, detalle = orden._sng_entregas_estado()
        valores['entrega_despachada'] = despachada
        valores['entrega_detalle'] = detalle or _('sin entregas')

        # Consulta de cortesia: le dice a quien autoriza cuantas copias hay ya.
        # Si falla no se bloquea nada; el control real corre en el agente.
        ok, datos, mensaje = self.env['sng.reimpresion.connector'].consultar(orden.id)
        valores['consulta_ok'] = ok
        valores['copias_previas'] = int(datos.get('copies') or 0) if ok else 0
        valores['consulta_error'] = '' if ok else mensaje
        return valores

    def _registrar(self, ok, motivo, datos, mensaje):
        """Escribe la bitacora en una transaccion propia.

        Un intento fallido termina en UserError, y eso revierte la transaccion
        del asistente. Si la bitacora se escribiera ahi, el fallo desapareceria
        justo cuando mas interesa dejarlo anotado. Con un cursor aparte, el
        registro queda aunque el usuario vea un error.
        """
        self.ensure_one()
        valores = {
            'order_id': self.order_id.id,
            'order_ref': self.order_id.name,
            'odoo_order_id': self.order_id.id,
            'user_id': self.env.user.id,
            'motivo': motivo,
            'resultado': 'ok' if ok else 'error',
            'detalle': json.dumps(datos, ensure_ascii=False) if ok else mensaje,
            'copias_previas': self.copias_previas,
            'entrega_despachada': self.entrega_despachada,
        }
        try:
            with self.env.registry.cursor() as cr:
                entorno = api.Environment(cr, SUPERUSER_ID, {})
                entorno['sng.reimpresion.log'].create(valores)
        except Exception:                                   # noqa: BLE001
            # Que falle la bitacora no debe tapar el resultado de la operacion.
            _logger.exception(
                'No se pudo registrar la reimpresion de %s', self.order_id.name)

    def action_confirmar(self):
        self.ensure_one()
        if not self.env.user.has_group(GRUPO):
            raise AccessError(_(
                'No tiene permiso para autorizar reimpresiones de ticket.'))

        motivo = (self.motivo or '').strip()
        if not motivo:
            raise UserError(_(
                'El motivo es obligatorio: sale impreso en el ticket y es lo '
                'que le explica a bodega por que hay una copia.'))

        quien = '%s <%s>' % (self.env.user.name, self.env.user.login)
        ok, datos, mensaje = self.env['sng.reimpresion.connector'].autorizar(
            self.order_id.id, quien, motivo)

        self._registrar(ok, motivo, datos, mensaje)

        if not ok:
            raise UserError(_(
                'No se pudo autorizar la reimpresion de %(orden)s.\n\n'
                '%(motivo)s\n\n'
                'El intento quedo registrado en la bitacora de reimpresiones.',
                orden=self.order_id.name, motivo=mensaje))

        copia = int(datos.get('copies') or self.copias_previas) + 1
        self.order_id.message_post(body=_(
            '<b>Reimpresion de ticket autorizada</b><br/>'
            'Motivo: %(motivo)s<br/>'
            'Saldra marcado como COPIA No.%(copia)s con el aviso '
            '<b>NO SURTIR DE NUEVO</b>.',
            motivo=motivo, copia=copia))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reimpresion autorizada'),
                'message': _(
                    'El ticket de %(orden)s va a salir en bodega marcado como '
                    'COPIA No.%(copia)s. La autorizacion es de un solo uso.',
                    orden=self.order_id.name, copia=copia),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
