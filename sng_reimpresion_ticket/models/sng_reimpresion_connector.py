"""Puente entre Odoo y el agente de impresion.

Dos caminos distintos, y confundirlos es lo que fallo el 09-sep-2026 con S43447:

  autorizar()          la orden YA se imprimio y hace falta otra copia. Escribe
                       /print_reprint_approvals/{orderId} via n8n. El agente
                       consume el token y saca un ticket marcado COPIA No.N.

  enviar_a_imprimir()  la orden NUNCA se imprimio, porque el webhook de Odoo no
                       llego a n8n o n8n fallo. No hay nada que reimprimir: hay
                       que volver a mandarla al flujo normal. Sale copia 1, sin
                       banner, y no consume ninguna autorizacion.

Autorizar la reimpresion de algo que nunca se imprimio no hace nada util: el
agente busca la orden en /print_queue, no la encuentra y registra
`autorizacion sin entrada en la cola`. El asistente elige el camino segun las
copias que reporta el ledger.

Odoo NO escribe en Firebase directamente. La credencial de la base en tiempo
real es de administrador total: quien la tenga puede borrar /print_ledger, que
es el registro que impide los tickets duplicados. Vive solo en n8n.

Contrato del webhook de reimpresion (doc/n8n_reprint_approval.workflow.json):

    peticion  {"token": str, "accion": "consultar"|"autorizar",
               "orderId": int, "approvedBy": str, "reason": str}
    respuesta {"ok": bool, "copies": int, "status": str, "orderName": str,
               "error": str}

El token viaja en el cuerpo, nunca en la URL, para que no quede en los logs de
acceso de ningun proxy intermedio.
"""
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT_POR_DEFECTO = 15

# La regla que dispara la impresion al confirmar. Se lee en vivo para sacar de
# ahi la URL del webhook, en vez de guardar una segunda copia que se puede
# desincronizar cuando alguien mueva la regla.
REGLA_IMPRESION = 'Imprimir ticket al confirmar orden'


class SngReimpresionConnector(models.AbstractModel):
    _name = 'sng.reimpresion.connector'
    _description = 'Puente hacia el agente de impresion de bodega'

    # ------------------------------------------------------------------
    # Configuracion
    # ------------------------------------------------------------------

    @api.model
    def _timeout(self):
        try:
            valor = int(self.env['ir.config_parameter'].sudo().get_param(
                'sng_reimpresion.timeout') or TIMEOUT_POR_DEFECTO)
        except (TypeError, ValueError):
            valor = TIMEOUT_POR_DEFECTO
        return max(valor, 1)

    @api.model
    def _configuracion(self):
        param = self.env['ir.config_parameter'].sudo()
        url = (param.get_param('sng_reimpresion.webhook_url') or '').strip()
        token = (param.get_param('sng_reimpresion.token') or '').strip()
        if not url or not token:
            raise UserError(_(
                'La reimpresion de tickets no esta configurada.\n\n'
                'Ventas -> Configuracion -> Ajustes -> Reimpresion de tickets '
                'de bodega: hay que indicar la URL del webhook y el token.'))
        return url, token, self._timeout()

    @api.model
    def _url_impresion(self):
        """A donde mandar una orden que nunca se imprimio.

        Si no hay una URL configurada a mano, se toma de la propia regla de
        automatizacion que Odoo usa al confirmar. Es la misma que ya funciona en
        produccion, y leerla evita mantener dos copias del mismo dato.
        """
        param = self.env['ir.config_parameter'].sudo()
        url = (param.get_param('sng_reimpresion.print_url') or '').strip()
        if url:
            return url
        regla = self.env['base.automation'].sudo().search(
            [('name', '=', REGLA_IMPRESION)], limit=1)
        for accion in regla.action_server_ids:
            if accion.state == 'webhook' and accion.webhook_url:
                return accion.webhook_url.strip()
        raise UserError(_(
            'No se a donde mandar la orden a imprimir.\n\n'
            'Configure la URL en Ventas -> Configuracion -> Ajustes -> '
            'Reimpresion de tickets de bodega, o revise que la regla "%s" siga '
            'teniendo su accion de webhook.') % REGLA_IMPRESION)

    # ------------------------------------------------------------------
    # Llamadas
    # ------------------------------------------------------------------

    @api.model
    def _llamar(self, payload):
        """Webhook de reimpresion. Devuelve (ok, datos, mensaje).

        Nunca levanta por un fallo de red: el llamador necesita registrar el
        intento fallido en la bitacora antes de avisarle al usuario.
        """
        url, token, timeout = self._configuracion()
        cuerpo = dict(payload, token=token)
        try:
            respuesta = requests.post(url, json=cuerpo, timeout=timeout)
        except requests.exceptions.Timeout:
            return False, {}, _(
                'El servicio de impresion no respondio en %s segundos.') % timeout
        except requests.exceptions.RequestException as exc:
            # El token va en el cuerpo, no en la URL: el texto de la excepcion
            # puede incluir la URL sin exponer la credencial.
            return False, {}, _(
                'No se pudo contactar el servicio de impresion: %s') % exc

        if respuesta.status_code in (401, 403):
            return False, {}, _(
                'El servicio de impresion rechazo el token configurado.')
        if respuesta.status_code >= 400:
            return False, {}, _(
                'El servicio de impresion respondio con codigo %s.'
            ) % respuesta.status_code

        try:
            datos = respuesta.json()
        except ValueError:
            return False, {}, _('El servicio de impresion devolvio una respuesta ilegible.')

        # n8n envuelve la salida en una lista cuando responde varios elementos.
        if isinstance(datos, list):
            datos = datos[0] if datos else {}
        if not isinstance(datos, dict):
            return False, {}, _('El servicio de impresion devolvio un formato inesperado.')

        if not datos.get('ok'):
            return False, datos, datos.get('error') or _(
                'El servicio de impresion rechazo la solicitud.')
        return True, datos, ''

    @api.model
    def consultar(self, order_id):
        """Estado de impresion de una orden. Best-effort: nunca levanta.

        `copies` es lo que decide si corresponde reimprimir o mandar a imprimir.
        Si Firebase o n8n no responden, el asistente lo dice y sigue permitiendo
        autorizar: el control real vive en el agente, no aca.
        """
        return self._llamar({'accion': 'consultar', 'orderId': int(order_id)})

    @api.model
    def autorizar(self, order_id, approved_by, reason):
        """Crea la autorizacion de un solo uso. Devuelve (ok, datos, mensaje)."""
        return self._llamar({
            'accion': 'autorizar',
            'orderId': int(order_id),
            'approvedBy': approved_by,
            'reason': reason,
        })

    @api.model
    def enviar_a_imprimir(self, order_id):
        """Reenvia la orden al flujo normal de impresion.

        Contrato distinto al del webhook de reimpresion: este es el mismo
        endpoint que dispara Odoo al confirmar y no devuelve `ok`, asi que se
        toma cualquier 2xx como aceptado. Aceptado significa que n8n recibio la
        orden, no que el papel ya salio: el agente imprime despues, cuando la
        orden aparece en la cola.
        """
        url = self._url_impresion()
        timeout = self._timeout()
        try:
            respuesta = requests.post(url, json={'id': int(order_id)}, timeout=timeout)
        except requests.exceptions.Timeout:
            return False, {}, _(
                'El servicio de impresion no respondio en %s segundos.') % timeout
        except requests.exceptions.RequestException as exc:
            return False, {}, _(
                'No se pudo contactar el servicio de impresion: %s') % exc

        if respuesta.status_code >= 400:
            return False, {}, _(
                'El servicio de impresion respondio con codigo %s.'
            ) % respuesta.status_code

        try:
            datos = respuesta.json()
            if isinstance(datos, list):
                datos = datos[0] if datos else {}
            if not isinstance(datos, dict):
                datos = {'respuesta': str(datos)[:200]}
        except ValueError:
            datos = {'respuesta': (respuesta.text or '')[:200]}
        datos.setdefault('accion', 'primera')
        datos.setdefault('orderId', int(order_id))
        return True, datos, ''
