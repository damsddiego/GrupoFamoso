# sng_mqtt_bus — Despliegue

Eventos en tiempo real Odoo → app_ruteros vía MQTT (Mosquitto self-hosted).
El bus solo AVISA ("cambió el cliente 15485"); los datos siguen viajando por
RPC como siempre.

## 1. Broker Mosquitto (VPS)

`docker-compose.yml`:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883"      # MQTT (poner detrás de firewall o usar 8883+TLS)
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
```

`mosquitto/config/mosquitto.conf`:

```
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl
persistence true
persistence_location /mosquitto/data/
```

Crear usuarios (uno para Odoo que publica, otro para las tabletas que solo
se suscriben):

```bash
docker exec mosquitto mosquitto_passwd -c -b /mosquitto/config/passwd odoo_pub  CAMBIAR_CLAVE_1
docker exec mosquitto mosquitto_passwd    -b /mosquitto/config/passwd app_sub   CAMBIAR_CLAVE_2
```

`mosquitto/config/acl`:

```
user odoo_pub
topic write ruteros/#

user app_sub
topic read ruteros/#
```

Reiniciar: `docker restart mosquitto`.

## 2. Servidor Odoo

```bash
pip3 install paho-mqtt
```

Instalar el módulo `sng_mqtt_bus` y en Ajustes → Técnico → Parámetros del
sistema crear:

| Clave                        | Valor                          |
|------------------------------|--------------------------------|
| `sng_mqtt_bus.host`          | IP/host del broker             |
| `sng_mqtt_bus.port`          | 1883                           |
| `sng_mqtt_bus.username`      | odoo_pub                       |
| `sng_mqtt_bus.password`      | CAMBIAR_CLAVE_1                |
| `sng_mqtt_bus.app_username`  | app_sub                        |
| `sng_mqtt_bus.app_password`  | CAMBIAR_CLAVE_2                |
| `sng_mqtt_bus.prefix`        | ruteros                        |
| `sng_mqtt_bus.tls`           | 0 (1 si se configura TLS)      |

Sin `sng_mqtt_bus.host`, el bus queda apagado y Odoo funciona normal.

## 3. Probar

```bash
# En el VPS: escuchar el topic
docker exec mosquitto mosquitto_sub -u app_sub -P CAMBIAR_CLAVE_2 -t 'ruteros/#' -v
```

Editar cualquier cliente en Odoo → debe aparecer
`ruteros/clientes {"id": 1234, "accion": "modificado", "ts": "..."}`.

## 4. La app

La app pide la configuración al hacer login (`sng.mqtt.bus.get_app_config`)
— recibe host/puerto/credenciales de solo-suscripción — y se suscribe a
`ruteros/clientes`. No hay que configurar nada en las tabletas.

Nota: en cada tableta conviene excluir la app del ahorro de batería para
que la conexión sobreviva en segundo plano.
