#!/usr/bin/env bash
# Setup del broker Mosquitto para sng_mqtt_bus.
# Genera claves aleatorias, crea los usuarios y levanta el contenedor.
# Ejecutar desde esta carpeta: bash setup.sh
set -euo pipefail

command -v docker >/dev/null || { echo "docker no está instalado"; exit 1; }

CLAVE_ODOO=$(openssl rand -hex 16)
CLAVE_APP=$(openssl rand -hex 16)

mkdir -p mosquitto/data mosquitto/log
touch mosquitto/config/passwd
chmod 700 mosquitto/config/passwd || true

docker compose up -d

# Esperar a que el contenedor esté arriba
sleep 3

docker exec mosquitto mosquitto_passwd -c -b /mosquitto/config/passwd odoo_pub "$CLAVE_ODOO"
docker exec mosquitto mosquitto_passwd    -b /mosquitto/config/passwd app_sub  "$CLAVE_APP"
docker exec mosquitto mosquitto_passwd    -b /mosquitto/config/passwd healthcheck healthcheck
docker exec mosquitto chown mosquitto:mosquitto /mosquitto/config/passwd
docker restart mosquitto

echo ""
echo "════════════════════════════════════════════════════════════"
echo " Broker listo. Parámetros de sistema para Odoo:"
echo "   sng_mqtt_bus.host          <IP o host de este VPS>"
echo "   sng_mqtt_bus.port          1883"
echo "   sng_mqtt_bus.username      odoo_pub"
echo "   sng_mqtt_bus.password      $CLAVE_ODOO"
echo "   sng_mqtt_bus.app_username  app_sub"
echo "   sng_mqtt_bus.app_password  $CLAVE_APP"
echo "   sng_mqtt_bus.prefix        ruteros"
echo "   sng_mqtt_bus.tls           0"
echo "════════════════════════════════════════════════════════════"
echo " GUARDA estas claves — no se vuelven a mostrar."
echo ""
echo " Probar (deja esta ventana escuchando y edita un cliente en Odoo):"
echo "   docker exec mosquitto mosquitto_sub -u app_sub -P $CLAVE_APP -t 'ruteros/#' -v"
