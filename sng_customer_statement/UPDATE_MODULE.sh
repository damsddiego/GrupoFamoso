#!/bin/bash
#
# Script para actualizar el módulo sng_customer_statement en Odoo 18
# Uso: ./UPDATE_MODULE.sh
#

MODULE_PATH="/opt/odoo18/odoo18-custom-addons/sng_customer_statement"
MODULE_NAME="sng_customer_statement"

echo "=========================================="
echo "Actualizando módulo: $MODULE_NAME"
echo "=========================================="

# Limpiar cache de Python
echo "Limpiando cache de Python..."
find "$MODULE_PATH" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$MODULE_PATH" -name "*.pyc" -delete 2>/dev/null || true
echo "✓ Cache limpiado"

echo ""
echo "CAMBIOS EN ESTA VERSIÓN (v18.0.1.1.0):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Agregada dependencia a 'sales_commission_omax'"
echo "✓ Ahora soporta completamente vendedores como contactos (is_salesperson)"
echo "✓ El filtro y agrupación por vendedor ahora funciona correctamente"
echo "✓ Detecta automáticamente el campo salesperson_id en facturas"
echo ""
echo "IMPORTANTE:"
echo "1. Pide a un usuario con permisos que reinicie el servidor Odoo:"
echo "   su -c 'systemctl restart odoo18'"
echo ""
echo "2. Luego actualiza el módulo desde la interfaz de Odoo:"
echo "   Apps > Quitar filtro 'Apps' > Buscar '$MODULE_NAME' > Actualizar"
echo ""
echo "=========================================="
echo "Preparación completada"
echo "=========================================="
