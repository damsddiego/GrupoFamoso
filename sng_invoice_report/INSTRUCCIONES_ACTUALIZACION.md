# Instrucciones para Actualizar el Módulo sng_invoice_report

## ⚠️ PROBLEMAS RESUELTOS

### 1. Carpeta duplicada eliminada:
- ❌ Eliminado: `/sng_invoice_report/sng_invoice_report/` (carpeta anidada obsoleta)
- ✅ Estructura correcta: `/sng_invoice_report/` (archivos actualizados en raíz)

### 2. Error "View types not defined tree":
- ❌ Error: `view_mode: 'tree,pivot,graph,form'` (nomenclatura antigua)
- ✅ Corregido: `view_mode: 'list,pivot,graph,form'` (Odoo 18)
- ✅ Agregado: Parámetro `views` explícito con tuplas
- ✅ Mejorado: Contexto con `allowed_company_ids`

## 📋 Pasos para Actualizar el Módulo

### Opción 1: Actualización Completa (RECOMENDADA)

```bash
# 1. Detener el servicio de Odoo
sudo systemctl stop odoo18

# 2. Limpiar cache de Python (ya ejecutado)
find /opt/odoo18/odoo18-custom-addons/sng_invoice_report -type d -name "__pycache__" -exec rm -rf {} +
find /opt/odoo18/odoo18-custom-addons/sng_invoice_report -name "*.pyc" -delete

# 3. Actualizar el módulo
/opt/odoo18/odoo18/odoo-bin -c /etc/odoo-server.conf \
    -u sng_invoice_report \
    -d NOMBRE_DE_TU_BASE_DE_DATOS \
    --stop-after-init

# 4. Reiniciar el servicio
sudo systemctl start odoo18
```

### Opción 2: Desde la Interfaz de Odoo

```bash
# 1. Detener Odoo
sudo systemctl stop odoo18

# 2. Iniciar Odoo normalmente
sudo systemctl start odoo18

# 3. Ir a Odoo en el navegador:
#    - Apps > Buscar "Invoice Report by Salesperson"
#    - Eliminar filtro "Apps" para ver módulos instalados
#    - Click en "Actualizar" (Upgrade)
```

### Opción 3: Modo Desarrollo

Si tienes activado el modo desarrollador:

```bash
# 1. Reiniciar Odoo completamente
sudo systemctl restart odoo18

# 2. En Odoo:
#    - Activar modo desarrollador (si no está activo)
#    - Apps > Actualizar Lista de Apps
#    - Buscar "sng_invoice_report"
#    - Click en "Actualizar"
```

## ✅ Verificación Post-Actualización

Después de actualizar, verifica que el wizard muestra:

1. ✓ Campo "Companies" (nuevo filtro multicompañía)
2. ✓ Botón azul "View on Screen" (acción principal)
3. ✓ Botones "Download Excel" y "Print PDF"

## 🆘 Si persiste el error

Si después de reiniciar Odoo aún aparece el error "company_ids no existe":

```bash
# Reinicio completo y forzado
sudo systemctl stop odoo18
sleep 5
sudo systemctl start odoo18

# Esperar 30 segundos y luego actualizar desde la interfaz
```

## 📝 Cambios Implementados

- ✅ Filtro multicompañía nativo
- ✅ Vista en pantalla (list, pivot, graph) - compatible Odoo 18
- ✅ Excel y PDF adaptados para multicompañía
- ✅ Sin uso de sudo() - respeta record rules
- ✅ Corrección de duplicación de credit notes
- ✅ Contexto mejorado con allowed_company_ids

## 🔍 Archivos Modificados

- `__manifest__.py` - v18.0.2.0.0 (actualizado)
- `wizard/invoice_report_wizard.py` - Lógica multicompañía
- `wizard/invoice_report_wizard_view.xml` - Nuevo campo company_ids
- `report/invoice_report_template.xml` - PDF multicompañía
- Eliminado: `sng_invoice_report/sng_invoice_report/` (duplicado)

---

**Autor:** Implementación de desarrollador senior Odoo 18
**Fecha:** 2026-03-09
**Versión:** 18.0.2.0.0
