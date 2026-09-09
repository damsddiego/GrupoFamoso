"""Asistente para volver a sacar el ticket de bodega de una orden.

Hay dos situaciones que se parecen desde la silla del usuario ("no tengo el
ticket") y necesitan acciones opuestas:

  copias >= 1   la orden se imprimio y el papel se perdio o salio mal.
                Corresponde AUTORIZAR una reimpresion: sale COPIA No.N.

  copias == 0   la orden nunca se imprimio, porque el webhook de Odoo no llego
                a n8n. No hay nada que reimprimir. Corresponde REENVIARLA al
                flujo normal: sale copia 1, sin banner y sin autorizacion.

Antes el asistente ofrecia siempre la reimpresion. El 09-sep-2026 Dennis la uso
tres veces sobre S43447, que nunca se habia impreso, y el agente respondio tres
veces `autorizacion sin entrada en la cola` sin sacar papel. El asistente le
mostraba "copias previas = 0" y aun asi lo dejaba seguir. Ahora ese numero
decide el camino en vez de ser un dato decorativo.

El tercer caso es el que no tiene salida desde aqui: nunca se imprimio Y la
mercaderia ya salio de bodega. Mandar un ticket de alistado para algo ya
despachado es el doble surtido que todo este control existe para evitar.
"""
import json
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

GRUPO = 'sng_reimpresion_ticket.group_reimpresion_ticket'


class SngReimpresionWizard(models.TransientModel):
    _name = 'sng.reimpresion.wizard'
    _description = 'Volver a sacar el ticket de bodega de una orden'

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
        help='Queda en la bitacora. En una reimpresion ademas sale impreso en '
             'el ticket, asi que escriba algo que le sirva a quien lo lea en '
             'bodega.',
    )

    modo = fields.Selection(
        selection=[
            ('reimpresion', 'Reimprimir: la orden ya se imprimio antes'),
            ('primera', 'Enviar a imprimir: nunca se imprimio'),
            ('bloqueado', 'Sin accion disponible'),
        ],
        string='Que corresponde',
        readonly=True,
        required=True,
        default='reimpresion',
    )

    copias_previas = fields.Integer(string='Copias ya impresas', readonly=True)
    consulta_ok = fields.Boolean(readonly=True)
    consulta_error = fields.Char(readonly=True)

    entrega_despachada = fields.Boolean(readonly=True)
    entrega_detalle = fields.Char(string='Entregas', readonly=True)

    # ------------------------------------------------------------------

    @api.model
    def _decidir_modo(self, consulta_ok, copias, despachada):
        """Que accion corresponde. Ver el docstring del modulo.

        Cuando la consulta falla no se puede distinguir un caso del otro, asi
        que se deja la reimpresion: el agente lleva su propia cuenta y numera
        la copia bien, y si resulta que no habia nada en la cola lo unico que
        pasa es que queda registrado el intento.
        """
        if not consulta_ok:
            return 'reimpresion'
        if copias >= 1:
            return 'reimpresion'
        return 'bloqueado' if despachada else 'primera'

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

        ok, datos, mensaje = self.env['sng.reimpresion.connector'].consultar(orden.id)
        copias = int(datos.get('copies') or 0) if ok else 0
        valores['consulta_ok'] = ok
        valores['copias_previas'] = copias
        valores['consulta_error'] = '' if ok else mensaje
        valores['modo'] = self._decidir_modo(ok, copias, despachada)
        return valores

    # ------------------------------------------------------------------

    def _verificar_permiso(self):
        if not self.env.user.has_group(GRUPO):
            raise AccessError(_(
                'No tiene permiso para volver a sacar tickets de bodega.'))

    def _motivo_valido(self):
        motivo = (self.motivo or '').strip()
        if not motivo:
            raise UserError(_(
                'El motivo es obligatorio: es lo que explica despues por que '
                'hubo un ticket de mas.'))
        return motivo

    def _registrar(self, accion, ok, motivo, datos, mensaje):
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
            'accion': accion,
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
                'No se pudo registrar la operacion sobre %s', self.order_id.name)

    def _notificar(self, titulo, mensaje):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': titulo,
                'message': mensaje,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ------------------------------------------------------------------

    def action_confirmar(self):
        """Autoriza una reimpresion: la orden ya se imprimio antes."""
        self.ensure_one()
        self._verificar_permiso()
        if self.modo != 'reimpresion':
            raise UserError(_(
                'Esta orden nunca se imprimio, asi que no hay copia que '
                'reimprimir. Cierre y vuelva a abrir el asistente.'))
        motivo = self._motivo_valido()

        quien = '%s <%s>' % (self.env.user.name, self.env.user.login)
        ok, datos, mensaje = self.env['sng.reimpresion.connector'].autorizar(
            self.order_id.id, quien, motivo)
        self._registrar('reimpresion', ok, motivo, datos, mensaje)

        if not ok:
            raise UserError(_(
                'No se pudo autorizar la reimpresion de %(orden)s.\n\n'
                '%(motivo)s\n\n'
                'El intento quedo registrado en la bitacora.',
                orden=self.order_id.name, motivo=mensaje))

        copia = int(datos.get('copies') or self.copias_previas) + 1
        self.order_id.message_post(body=_(
            '<b>Reimpresion de ticket autorizada</b><br/>'
            'Motivo: %(motivo)s<br/>'
            'Saldra marcado como COPIA No.%(copia)s con el aviso '
            '<b>NO SURTIR DE NUEVO</b>.',
            motivo=motivo, copia=copia))

        return self._notificar(_('Reimpresion autorizada'), _(
            'El ticket de %(orden)s va a salir en bodega marcado como '
            'COPIA No.%(copia)s. La autorizacion es de un solo uso.',
            orden=self.order_id.name, copia=copia))

    def action_enviar_impresion(self):
        """Reenvia al flujo normal una orden que nunca llego a imprimirse."""
        self.ensure_one()
        self._verificar_permiso()
        if self.modo != 'primera':
            raise UserError(_(
                'Esta orden no esta en el caso de "nunca se imprimio". Cierre '
                'y vuelva a abrir el asistente.'))
        motivo = self._motivo_valido()

        # La entrega pudo cerrarse mientras el asistente estaba abierto. Se
        # vuelve a mirar aca porque este es el punto sin retorno.
        despachada, detalle = self.order_id._sng_entregas_estado()
        if despachada:
            raise UserError(_(
                'La mercaderia de %(orden)s ya salio de bodega (%(entregas)s).\n\n'
                'Un ticket de alistado para una orden ya despachada puede hacer '
                'que se surta dos veces, asi que no se envia.',
                orden=self.order_id.name, entregas=detalle))

        ok, datos, mensaje = self.env['sng.reimpresion.connector'].enviar_a_imprimir(
            self.order_id.id)
        self._registrar('primera', ok, motivo, datos, mensaje)

        if not ok:
            raise UserError(_(
                'No se pudo enviar %(orden)s a imprimir.\n\n'
                '%(motivo)s\n\n'
                'El intento quedo registrado en la bitacora.',
                orden=self.order_id.name, motivo=mensaje))

        self.order_id.message_post(body=_(
            '<b>Orden reenviada a imprimir</b><br/>'
            'Motivo: %(motivo)s<br/>'
            'Nunca se habia impreso, asi que sale como ticket normal, sin marca '
            'de copia.', motivo=motivo))

        return self._notificar(_('Enviada a imprimir'), _(
            '%(orden)s se mando al flujo de impresion. El ticket sale en bodega '
            'en unos segundos, como ticket normal. Si no aparece, avise: '
            'significa que la orden no esta llegando a la cola.',
            orden=self.order_id.name))
