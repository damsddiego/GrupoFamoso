"""Puente entre Odoo y el agente de impresion.

Odoo NO escribe en Firebase directamente. Llama a un webhook de n8n, que es
quien guarda la credencial de la base de datos en tiempo real. Esa credencial es
de administrador total: quien la tenga puede borrar /print_ledger, que es
justamente el registro que impide los tickets duplicados. Manteniendola fuera de
Odoo, un administrador de Odoo no gana ningun poder sobre el control.

Contrato con el webhook (ver doc/n8n_reprint_approval.workflow.json):

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


class SngReimpresionConnector(models.AbstractModel):
    _name = 'sng.reimpresion.connector'
    _description = 'Puente hacia el agente de impresion de bodega'

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
        try:
            timeout = int(param.get_param('sng_reimpresion.timeout') or TIMEOUT_POR_DEFECTO)
        except (TypeError, ValueError):
            timeout = TIMEOUT_POR_DEFECTO
        return url, token, max(timeout, 1)

    @api.model
    def _llamar(self, payload):
        """Devuelve (ok, datos, mensaje).

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

        Se usa para mostrarle a quien autoriza cuantas copias existen ya. Si
        Firebase o n8n no responden, el asistente lo dice y sigue permitiendo
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
