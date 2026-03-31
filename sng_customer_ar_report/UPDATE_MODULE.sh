#!/bin/bash
# Script para actualizar el módulo sng_customer_ar_report

MODULE_NAME="sng_customer_ar_report"
MODULE_PATH="/opt/odoo18/odoo18-custom-addons/${MODULE_NAME}"

echo "========================================"
echo "Actualizando módulo: ${MODULE_NAME}"
echo "========================================"

# 1. Limpiar cache de Python
echo "1. Limpiando cache de Python..."
find "${MODULE_PATH}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find "${MODULE_PATH}" -name "*.pyc" -delete
echo "   ✓ Cache limpiado"

# 2. Validar sintaxis Python
echo "2. Validando sintaxis Python..."
python3 -m py_compile "${MODULE_PATH}"/models/*.py
python3 -m py_compile "${MODULE_PATH}"/wizard/*.py
echo "   ✓ Sintaxis Python OK"

# 3. Validar XML
echo "3. Validando archivos XML..."
python3 -c "import xml.etree.ElementTree as ET; ET.parse('${MODULE_PATH}/views/sng_customer_ar_report_views.xml'); print('   ✓ XML views OK')"
python3 -c "import xml.etree.ElementTree as ET; ET.parse('${MODULE_PATH}/views/sng_customer_ar_report_wizard_views.xml'); print('   ✓ XML wizard views OK')"

echo ""
echo "========================================"
echo "Módulo validado correctamente"
echo "========================================"
echo ""
echo "IMPORTANTE: Este script NO reinicia Odoo porque el usuario odoo18 no tiene permisos sudo."
echo ""
echo "Para completar la actualización, ejecuta los siguientes pasos:"
echo ""
echo "1. Solicita a un administrador que reinicie Odoo:"
echo "   sudo systemctl restart odoo18"
echo ""
echo "2. Luego actualiza el módulo desde la UI de Odoo:"
echo "   - Ve a Apps"
echo "   - Quita el filtro 'Apps'"
echo "   - Busca '${MODULE_NAME}'"
echo "   - Click en 'Upgrade'"
echo ""
