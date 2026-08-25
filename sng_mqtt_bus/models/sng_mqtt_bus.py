# -*- coding: utf-8 -*-
"""Bus MQTT para eventos hacia la app app_ruteros.

Publica mensajes JSON pequeños ("cambió el cliente X") a un broker MQTT
self-hosted (Mosquitto). La app está suscrita y, al recibir el aviso,
sincroniza ese registro puntual por RPC como siempre — el bus solo AVISA,
nunca transporta los datos.

Configuración (Ajustes → Técnico → Parámetros del sistema):
- sng_mqtt_bus.host        (obligatorio; sin él, el bus queda apagado)
- sng_mqtt_bus.port        (default 1883; 8883 con TLS)
- sng_mqtt_bus.username    (usuario del broker para Odoo)
- sng_mqtt_bus.password
- sng_mqtt_bus.tls         ('1' para TLS, default '0')
- sng_mqtt_bus.prefix      (prefijo de topics, default 'ruteros')
- sng_mqtt_bus.app_username / sng_mqtt_bus.app_password
    Credenciales (solo-suscripción) que la app usa para conectarse;
    se entregan vía get_app_config().
"""
import json
import logging

from odoo import api, models, fields

_logger = logging.getLogger(__name__)

try:
    from paho.mqtt import publish as mqtt_publish
except ImportError:  # pragma: no cover
    mqtt_publish = None
    _logger.warning('sng_mqtt_bus: paho-mqtt no está instalado; '
                    'el bus queda desactivado (pip install paho-mqtt)')


class SngMqttBus(models.AbstractModel):
    _name = 'sng.mqtt.bus'
    _description = 'Bus MQTT para la app de ruteros'

    @api.model
    def _config(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        host = (get('sng_mqtt_bus.host') or '').strip()
        if not host:
            return None
        return {
            'host': host,
            'port': int(get('sng_mqtt_bus.port') or 1883),
            'username': get('sng_mqtt_bus.username') or None,
            'password': get('sng_mqtt_bus.password') or None,
            'tls': (get('sng_mqtt_bus.tls') or '0') == '1',
            'prefix': (get('sng_mqtt_bus.prefix') or 'ruteros').strip('/'),
        }

    @api.model
    def get_app_config(self):
        """Configuración de conexión para la APP (la llama por RPC al hacer
        login). Entrega las credenciales de solo-suscripción, nunca las del
        publicador. Retorna {} si el bus no está configurado.

        Las tabletas pueden entrar por un camino distinto al de Odoo (p. ej.
        WebSocket detrás de un túnel cloudflared mientras Odoo publica por
        TCP interno). Parámetros propios de la app, con fallback al del
        publicador:
        - sng_mqtt_bus.app_host     (default: sng_mqtt_bus.host)
        - sng_mqtt_bus.app_port     (default: sng_mqtt_bus.port; 443 con túnel)
        - sng_mqtt_bus.app_ws       ('1' = MQTT sobre WebSocket)
        - sng_mqtt_bus.app_ws_path  (default '/mqtt')
        - sng_mqtt_bus.app_tls      (default: '1' si ws — wss://; si no, tls
                                     del publicador)
        """
        cfg = self._config()
        if not cfg:
            return {}
        get = self.env['ir.config_parameter'].sudo().get_param
        ws = (get('sng_mqtt_bus.app_ws') or '0') == '1'
        app_tls_param = get('sng_mqtt_bus.app_tls')
        if app_tls_param is not None and app_tls_param is not False:
            app_tls = app_tls_param == '1'
        else:
            app_tls = True if ws else cfg['tls']
        return {
            'host': (get('sng_mqtt_bus.app_host') or cfg['host']).strip(),
            'port': int(get('sng_mqtt_bus.app_port') or cfg['port']),
            'tls': app_tls,
            'ws': ws,
            'ws_path': get('sng_mqtt_bus.app_ws_path') or '/mqtt',
            'prefix': cfg['prefix'],
            'username': get('sng_mqtt_bus.app_username') or '',
            'password': get('sng_mqtt_bus.app_password') or '',
        }

    @api.model
    def publicar(self, subtopic, payload):
        """Encola la publicación para DESPUÉS del commit: si la transacción
        falla no se emite nada, y la latencia del guardado en Odoo no
        depende del broker. Cualquier error solo se loguea — el bus jamás
        rompe una operación de negocio."""
        cfg = self._config()
        if not cfg or mqtt_publish is None:
            return
        topic = '%s/%s' % (cfg['prefix'], subtopic.strip('/'))
        payload = dict(payload, ts=fields.Datetime.now().isoformat())
        cuerpo = json.dumps(payload, default=str)

        def _enviar():
            try:
                auth = None
                if cfg['username']:
                    auth = {'username': cfg['username'],
                            'password': cfg['password'] or ''}
                tls = {'ca_certs': None} if cfg['tls'] else None
                mqtt_publish.single(
                    topic,
                    payload=cuerpo,
                    qos=1,
                    retain=False,
                    hostname=cfg['host'],
                    port=cfg['port'],
                    auth=auth,
                    tls=tls,
                    keepalive=10,
                )
                _logger.debug('sng_mqtt_bus: publicado %s %s', topic, cuerpo)
            except Exception as e:  # noqa: BLE001
                _logger.warning('sng_mqtt_bus: no se pudo publicar %s: %s',
                                topic, e)

        self.env.cr.postcommit.add(_enviar)
