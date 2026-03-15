#!/bin/bash
# Script para actualizar el módulo sales_commission_omax

echo "======================================"
echo "Actualizando módulo sales_commission_omax"
echo "======================================"

# Limpiar archivos pyc y cache
echo "1. Limpiando archivos cache..."
find /opt/odoo18/odoo18-custom-addons/sales_commission_omax -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /opt/odoo18/odoo18-custom-addons/sales_commission_omax -name "*.pyc" -delete 2>/dev/null

echo "2. Verificando sintaxis Python..."
python3 -m py_compile /opt/odoo18/odoo18-custom-addons/sales_commission_omax/models/sale_order.py

if [ $? -eq 0 ]; then
    echo "✓ Sintaxis correcta"
else
    echo "✗ Error de sintaxis"
    exit 1
fi

echo ""
echo "======================================"
echo "SIGUIENTE PASO:"
echo "======================================"
echo "Reinicia el servicio de Odoo y actualiza el módulo desde la interfaz:"
echo ""
echo "1. Reiniciar Odoo:"
echo "   sudo systemctl restart odoo18"
echo ""
echo "2. Actualizar módulo en Odoo:"
echo "   - Ve a Aplicaciones"
echo "   - Busca 'sales_commission_omax'"
echo "   - Haz clic en 'Actualizar'"
echo ""
echo "NOTA: El campo 'Vendedor (Contacto)' ahora mostrará solo vendedores"
echo "      asignados al cliente (contactos con is_salesperson=True)"
echo "======================================"
