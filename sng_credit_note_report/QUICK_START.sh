#!/bin/bash
################################################################################
# SNG Credit Note Report - Quick Start Script
#
# Este script automatiza la instalación del módulo en Odoo 18
#
# Uso:
#   chmod +x QUICK_START.sh
#   ./QUICK_START.sh
#
################################################################################

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     SNG Credit Note Report - Instalación Rápida          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Paso 1: Verificar Python
echo -e "${YELLOW}[1/5] Verificando Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ Python encontrado: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3 no encontrado. Por favor instale Python 3.${NC}"
    exit 1
fi

# Paso 2: Instalar xlsxwriter
echo -e "\n${YELLOW}[2/5] Instalando librería xlsxwriter...${NC}"
pip3 install xlsxwriter --quiet 2>/dev/null || pip install xlsxwriter --quiet 2>/dev/null
if python3 -c "import xlsxwriter" 2>/dev/null; then
    echo -e "${GREEN}✓ xlsxwriter instalado correctamente${NC}"
else
    echo -e "${RED}✗ Error al instalar xlsxwriter${NC}"
    echo -e "${YELLOW}  Intente manualmente: pip install xlsxwriter${NC}"
    exit 1
fi

# Paso 3: Verificar estructura del módulo
echo -e "\n${YELLOW}[3/5] Verificando estructura del módulo...${NC}"
MODULE_PATH="/opt/odoo18/odoo18-custom-addons/sng_credit_note_report"
if [ -f "$MODULE_PATH/__manifest__.py" ]; then
    echo -e "${GREEN}✓ Módulo encontrado en: $MODULE_PATH${NC}"
else
    echo -e "${RED}✗ Módulo no encontrado en: $MODULE_PATH${NC}"
    exit 1
fi

# Verificar archivos clave
FILES=("models/sng_credit_note_report.py" "wizard/sng_credit_note_export_wizard.py" "security/ir.model.access.csv")
for file in "${FILES[@]}"; do
    if [ -f "$MODULE_PATH/$file" ]; then
        echo -e "${GREEN}  ✓ $file${NC}"
    else
        echo -e "${RED}  ✗ $file no encontrado${NC}"
        exit 1
    fi
done

# Paso 4: Verificar sintaxis Python
echo -e "\n${YELLOW}[4/5] Validando sintaxis Python...${NC}"
python3 -m py_compile "$MODULE_PATH/models/sng_credit_note_report.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Modelo principal: sintaxis correcta${NC}"
else
    echo -e "${RED}✗ Error de sintaxis en el modelo principal${NC}"
    exit 1
fi

python3 -m py_compile "$MODULE_PATH/wizard/sng_credit_note_export_wizard.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Wizard: sintaxis correcta${NC}"
else
    echo -e "${RED}✗ Error de sintaxis en el wizard${NC}"
    exit 1
fi

# Paso 5: Instrucciones finales
echo -e "\n${YELLOW}[5/5] Próximos pasos:${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  INSTALACIÓN EN ODOO                                      ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}║  Método 1: Desde la interfaz web (Recomendado)           ║${NC}"
echo -e "${BLUE}║  ───────────────────────────────────────────────────────  ║${NC}"
echo -e "${BLUE}║  1. Acceder a Odoo como administrador                     ║${NC}"
echo -e "${BLUE}║  2. Ir a: Aplicaciones                                    ║${NC}"
echo -e "${BLUE}║  3. Menú (☰) → Actualizar Lista de Aplicaciones          ║${NC}"
echo -e "${BLUE}║  4. Buscar: 'SNG Credit Note Report'                      ║${NC}"
echo -e "${BLUE}║  5. Clic en 'Instalar'                                    ║${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}║  Método 2: Desde línea de comandos                        ║${NC}"
echo -e "${BLUE}║  ───────────────────────────────────────────────────────  ║${NC}"
echo -e "${BLUE}║  Edite el comando según su configuración:                 ║${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${GREEN}║  odoo-bin -c /etc/odoo.conf \\                             ${BLUE}║${NC}"
echo -e "${GREEN}║           -d YOUR_DATABASE \\                              ${BLUE}║${NC}"
echo -e "${GREEN}║           -i sng_credit_note_report                       ${BLUE}║${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║  VERIFICACIÓN                                             ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}║  Ir a: Contabilidad → Reportes → Notas de Crédito (SNG) ║${NC}"
echo -e "${BLUE}║                                                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${GREEN}✓ Pre-requisitos verificados correctamente${NC}"
echo -e "${GREEN}✓ El módulo está listo para ser instalado en Odoo 18${NC}"
echo ""
echo -e "${YELLOW}📚 Para más información, consulte:${NC}"
echo -e "   - README.md (documentación completa)"
echo -e "   - INSTALL.md (guía de instalación detallada)"
echo -e "   - RESUMEN_TECNICO.md (detalles técnicos)"
echo ""
