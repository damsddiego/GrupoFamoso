#!/bin/bash
###############################################################################
# Script de Instalación Rápida
# Módulo: sng_sale_hide_orders_with_invoice
# Versión: 18.0.1.0.0
# Autor: SNG Development Team
###############################################################################

set -e  # Detener en caso de error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables de configuración (AJUSTAR SEGÚN TU ENTORNO)
ODOO_BIN="/opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin"
ODOO_CONF="/etc/odoo18.conf"
ODOO_USER="odoo18"
MODULE_NAME="sng_sale_hide_orders_with_invoice"
MODULE_PATH="/opt/odoo18/odoo18-custom-addons/$MODULE_NAME"

###############################################################################
# Funciones
###############################################################################

print_header() {
    echo -e "${BLUE}"
    echo "================================================================================"
    echo "  INSTALACIÓN MÓDULO: sng_sale_hide_orders_with_invoice"
    echo "================================================================================"
    echo -e "${NC}"
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

check_prerequisites() {
    print_step "Verificando pre-requisitos..."

    # Verificar que el usuario actual tiene permisos
    if [ "$EUID" -ne 0 ] && [ "$(whoami)" != "$ODOO_USER" ]; then
        print_error "Este script debe ejecutarse como root o como usuario $ODOO_USER"
        exit 1
    fi

    # Verificar que el módulo existe
    if [ ! -d "$MODULE_PATH" ]; then
        print_error "Módulo no encontrado en: $MODULE_PATH"
        exit 1
    fi
    print_success "Módulo encontrado en: $MODULE_PATH"

    # Verificar archivos principales
    local required_files=(
        "$MODULE_PATH/__init__.py"
        "$MODULE_PATH/__manifest__.py"
        "$MODULE_PATH/models/sale_order.py"
        "$MODULE_PATH/views/sale_order_views.xml"
        "$MODULE_PATH/security/ir.model.access.csv"
    )

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Archivo faltante: $file"
            exit 1
        fi
    done
    print_success "Todos los archivos necesarios están presentes"

    # Verificar configuración de Odoo
    if [ ! -f "$ODOO_CONF" ]; then
        print_error "Archivo de configuración no encontrado: $ODOO_CONF"
        exit 1
    fi
    print_success "Configuración de Odoo encontrada: $ODOO_CONF"
}

check_database() {
    print_step "Verificando base de datos..."

    if [ -z "$DB_NAME" ]; then
        print_info "No se especificó base de datos. Listando bases disponibles:"
        echo ""

        # Intentar listar bases de datos
        sudo -u postgres psql -l 2>/dev/null | grep -E '^\s+\w+' | awk '{print "  - " $1}' || {
            print_error "No se pudo listar bases de datos"
            echo ""
            echo "Por favor, ejecuta el script especificando la base de datos:"
            echo "  sudo bash quick_install.sh nombre_base_datos"
            exit 1
        }

        echo ""
        print_error "Debes especificar una base de datos"
        echo "Uso: sudo bash quick_install.sh nombre_base_datos"
        exit 1
    fi

    # Verificar que la base de datos existe
    if ! sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        print_error "Base de datos '$DB_NAME' no encontrada"
        exit 1
    fi

    print_success "Base de datos '$DB_NAME' encontrada"
}

verify_module_syntax() {
    print_step "Verificando sintaxis de archivos Python..."

    python3 -m py_compile "$MODULE_PATH/__manifest__.py" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "__manifest__.py OK"
    else
        print_error "__manifest__.py tiene errores de sintaxis"
        exit 1
    fi

    python3 -m py_compile "$MODULE_PATH/models/sale_order.py" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "models/sale_order.py OK"
    else
        print_error "models/sale_order.py tiene errores de sintaxis"
        exit 1
    fi
}

install_module() {
    print_step "Instalando módulo en base de datos '$DB_NAME'..."

    echo ""
    print_info "Ejecutando: odoo-bin -i $MODULE_NAME -d $DB_NAME --stop-after-init"
    echo ""

    if [ "$(whoami)" == "root" ]; then
        sudo -u $ODOO_USER $ODOO_BIN \
            -c $ODOO_CONF \
            -d "$DB_NAME" \
            -i $MODULE_NAME \
            --stop-after-init \
            --log-level=info
    else
        $ODOO_BIN \
            -c $ODOO_CONF \
            -d "$DB_NAME" \
            -i $MODULE_NAME \
            --stop-after-init \
            --log-level=info
    fi

    if [ $? -eq 0 ]; then
        print_success "Módulo instalado correctamente"
    else
        print_error "Error al instalar el módulo"
        exit 1
    fi
}

restart_odoo() {
    print_step "Reiniciando servicio de Odoo..."

    if systemctl is-active --quiet odoo18; then
        sudo systemctl restart odoo18
        sleep 3

        if systemctl is-active --quiet odoo18; then
            print_success "Servicio odoo18 reiniciado correctamente"
        else
            print_error "Error al reiniciar servicio odoo18"
            echo "Revisar logs: sudo journalctl -u odoo18 -n 50"
            exit 1
        fi
    else
        print_info "Servicio odoo18 no está ejecutándose como systemd service"
        print_info "Por favor, reinicia Odoo manualmente"
    fi
}

run_tests() {
    print_step "Ejecutando tests de verificación..."

    local test_script="/tmp/test_${MODULE_NAME}.py"

    cat > "$test_script" << 'EOF'
# Test de verificación post-instalación
try:
    # 1. Verificar módulo instalado
    module = env['ir.module.module'].search([
        ('name', '=', 'sng_sale_hide_orders_with_invoice')
    ])
    assert module.state == 'installed', f"Módulo no instalado (estado: {module.state})"
    print("✅ Módulo instalado")

    # 2. Verificar campo has_invoice
    field = env['ir.model.fields'].search([
        ('model', '=', 'sale.order'),
        ('name', '=', 'has_invoice')
    ])
    assert field, "Campo has_invoice no encontrado"
    assert field.store, "Campo has_invoice no almacenado"
    print("✅ Campo 'has_invoice' existe y está almacenado")

    # 3. Verificar acción y filtro
    action = env.ref('sale.action_orders_to_invoice')
    context_str = str(action.context)
    assert 'search_default_hide_with_invoices' in context_str, "Context no modificado"
    print("✅ Acción modificada correctamente")
    print(f"   Context: {action.context}")

    # 4. Verificar filtro en search view
    view = env.ref('sng_sale_hide_orders_with_invoice.view_sales_order_filter_hide_with_invoices')
    assert view, "Vista de filtro no encontrada"
    print("✅ Filtro 'Sin facturas generadas' creado correctamente")

    # 5. Verificar órdenes
    orders = env['sale.order'].search([('invoice_status', '=', 'to invoice')])
    with_invoices = orders.filtered(lambda o: o.has_invoice)
    without_invoices = orders.filtered(lambda o: not o.has_invoice)

    print(f"✅ Órdenes analizadas:")
    print(f"   Total pendientes: {len(orders)}")
    print(f"   Sin facturas: {len(without_invoices)}")
    print(f"   Con facturas: {len(with_invoices)}")

    print("\n🎉 TODOS LOS TESTS PASARON 🎉")

except Exception as e:
    print(f"❌ ERROR EN TESTS: {e}")
    import traceback
    traceback.print_exc()
EOF

    print_info "Ejecutando tests..."
    echo ""

    if [ "$(whoami)" == "root" ]; then
        sudo -u $ODOO_USER $ODOO_BIN shell \
            -c $ODOO_CONF \
            -d "$DB_NAME" < "$test_script"
    else
        $ODOO_BIN shell \
            -c $ODOO_CONF \
            -d "$DB_NAME" < "$test_script"
    fi

    if [ $? -eq 0 ]; then
        print_success "Tests completados"
    else
        print_error "Tests fallidos"
    fi

    rm -f "$test_script"
}

print_summary() {
    echo ""
    echo -e "${GREEN}"
    echo "================================================================================"
    echo "  INSTALACIÓN COMPLETADA"
    echo "================================================================================"
    echo -e "${NC}"
    echo ""
    echo "El módulo 'sng_sale_hide_orders_with_invoice' ha sido instalado en '$DB_NAME'"
    echo ""
    echo "📋 Próximos pasos:"
    echo ""
    echo "  1. Acceder a Odoo: http://tu-servidor:8069"
    echo "  2. Ir a: Ventas → Órdenes → Pendiente por facturar"
    echo "  3. Verificar que solo aparecen órdenes SIN facturas"
    echo ""
    echo "📖 Documentación:"
    echo ""
    echo "  - README.md: Documentación completa"
    echo "  - TESTING.md: Scripts de prueba"
    echo "  - INSTALL.md: Guía de instalación detallada"
    echo "  - TECHNICAL_SUMMARY.md: Análisis técnico"
    echo ""
    echo "🧪 Tests adicionales:"
    echo ""
    echo "  # Crear orden sin factura (debe aparecer)"
    echo "  # Crear orden con factura (NO debe aparecer)"
    echo ""
    echo "🐛 Troubleshooting:"
    echo ""
    echo "  sudo journalctl -u odoo18 -f     # Ver logs en tiempo real"
    echo "  tail -f /var/log/odoo18/odoo.log  # Ver logs de Odoo"
    echo ""
    echo -e "${GREEN}¡Instalación exitosa!${NC}"
    echo ""
}

###############################################################################
# MAIN
###############################################################################

main() {
    # Capturar nombre de base de datos del primer argumento
    DB_NAME="${1:-}"

    print_header

    check_prerequisites
    check_database
    verify_module_syntax
    install_module
    restart_odoo
    run_tests
    print_summary
}

# Ejecutar script principal
main "$@"
