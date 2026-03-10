#!/bin/bash
#
# Script para actualizar el módulo sng_invoice_report en Odoo 18
# Uso: ./UPDATE_MODULE.sh [nombre_base_datos]
#

MODULE_PATH="/opt/odoo18/odoo18-custom-addons/sng_invoice_report"
MODULE_NAME="sng_invoice_report"

echo "=========================================="
echo "Actualizando módulo: $MODULE_NAME"
echo "=========================================="

# Limpiar cache de Python
echo "Limpiando cache de Python..."
find "$MODULE_PATH" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$MODULE_PATH" -name "*.pyc" -delete 2>/dev/null || true
echo "✓ Cache limpiado"

echo ""
echo "IMPORTANTE:"
echo "1. Asegúrate de reiniciar el servidor Odoo completamente"
echo "2. Luego actualiza el módulo desde Apps > Buscar '$MODULE_NAME' > Actualizar"
echo ""
echo "O ejecuta manualmente:"
echo "   odoo-bin -c /etc/odoo-server.conf -u $MODULE_NAME -d TU_BASE_DATOS --stop-after-init"
echo ""
echo "=========================================="
echo "Preparación completada"
echo "=========================================="
