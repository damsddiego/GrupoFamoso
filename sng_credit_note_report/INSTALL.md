# Guía de Instalación Rápida - SNG Credit Note Report

## 📋 Pre-requisitos

1. **Odoo 18 Community** instalado y funcionando
2. **Módulo account** instalado (viene por defecto)
3. **Librería xlsxwriter** para exportación Excel

## 🚀 Instalación en 3 Pasos

### Paso 1: Instalar dependencia Python

```bash
# Con pip
pip install xlsxwriter

# O con pip3
pip3 install xlsxwriter

# O en entorno virtual de Odoo
/path/to/odoo/venv/bin/pip install xlsxwriter
```

### Paso 2: Copiar el módulo

El módulo ya está en: `/opt/odoo18/odoo18-custom-addons/sng_credit_note_report`

Si necesitas moverlo:
```bash
# Copiar a otra ubicación de addons
cp -r /opt/odoo18/odoo18-custom-addons/sng_credit_note_report /path/to/your/addons/

# O crear un symlink
ln -s /opt/odoo18/odoo18-custom-addons/sng_credit_note_report /path/to/your/addons/
```

### Paso 3: Instalar en Odoo

**Opción A: Desde la interfaz web (recomendado)**

1. Acceder a Odoo como administrador
2. Ir a **Aplicaciones**
3. Hacer clic en el menú ☰ → **Actualizar Lista de Aplicaciones**
4. Confirmar la actualización
5. Buscar "**SNG Credit Note Report**"
6. Hacer clic en **Instalar**
7. Esperar a que se complete la instalación

**Opción B: Desde línea de comandos**

```bash
# Método 1: Con -i (instalar)
odoo-bin -c /etc/odoo.conf -d your_database -i sng_credit_note_report

# Método 2: Con --init
odoo-bin -c /etc/odoo.conf -d your_database --init=sng_credit_note_report
```

## ✅ Verificación

### 1. Verificar que el módulo está instalado

```bash
# Conectar a PostgreSQL
psql -U odoo -d your_database

# Verificar estado del módulo
SELECT name, state FROM ir_module_module WHERE name = 'sng_credit_note_report';
```

Debería mostrar: `state = 'installed'`

### 2. Verificar que la vista SQL fue creada

```sql
SELECT COUNT(*) FROM pg_views WHERE viewname = 'sng_credit_note_report';
```

Debería retornar: `1`

### 3. Verificar acceso al menú

1. Ir a **Contabilidad** (icono en el menú principal)
2. Hacer clic en **Reportes** en el menú superior
3. Debe aparecer **Notas de Crédito (SNG)**

### 4. Probar el reporte

1. Hacer clic en **Notas de Crédito (SNG)**
2. Debería mostrar todas las notas de crédito publicadas
3. Si no hay datos, es normal si no tienes notas de crédito registradas

## 🔧 Solución de Problemas

### ❌ Error: "xlsxwriter module not found"

**Causa:** La librería xlsxwriter no está instalada

**Solución:**
```bash
# Encontrar el Python que usa Odoo
which odoo-bin
# O
ps aux | grep odoo

# Instalar con el pip correcto
pip install xlsxwriter

# Si usas virtualenv
source /path/to/odoo/venv/bin/activate
pip install xlsxwriter
```

### ❌ No aparece el menú

**Causa 1:** El usuario no tiene permisos de contabilidad

**Solución:**
1. Ir a **Configuración → Usuarios y Compañías → Usuarios**
2. Editar el usuario
3. En **Derechos de Acceso**, asignar:
   - **Contabilidad: Facturación** (mínimo)
   - O **Contabilidad: Administrador**

**Causa 2:** El módulo no está instalado correctamente

**Solución:**
```bash
# Actualizar el módulo
odoo-bin -c /etc/odoo.conf -d your_database -u sng_credit_note_report

# Ver logs para detectar errores
tail -f /var/log/odoo/odoo-server.log
```

### ❌ Error al crear la vista SQL

**Causa:** El campo `unique_id` no existe en `res.partner`

**Solución Temporal:** Modificar el archivo [models/sng_credit_note_report.py](models/sng_credit_note_report.py)

Buscar la línea:
```python
rp.unique_id AS partner_unique_id,
```

Reemplazar por una de estas opciones:

```python
# Opción 1: Usar el VAT/NIF
rp.vat AS partner_unique_id,

# Opción 2: Usar la referencia interna
rp.ref AS partner_unique_id,

# Opción 3: Usar el ID numérico
CAST(rp.id AS VARCHAR) AS partner_unique_id,

# Opción 4: Dejar vacío
'' AS partner_unique_id,
```

Luego actualizar el módulo:
```bash
odoo-bin -c /etc/odoo.conf -d your_database -u sng_credit_note_report
```

### ❌ La columna "Facturas Relacionadas" está vacía

**Causa:** Las notas de crédito no están reconciliadas con facturas

**Verificación:**
1. Ir a **Contabilidad → Clientes → Facturas**
2. Abrir una factura que tenga una nota de crédito
3. En la pestaña **Información de factura**, ver el campo **Créditos**
4. Si está vacío, la NC no está reconciliada

**Solución:** Reconciliar manualmente
1. Ir a **Contabilidad → Contabilidad → Reconciliación**
2. Seleccionar el cliente
3. Marcar la factura y la nota de crédito
4. Hacer clic en **Reconciliar**

## 📊 Uso Rápido

### Ver el reporte
```
Contabilidad → Reportes → Notas de Crédito (SNG)
```

### Exportar a Excel
1. Aplicar filtros deseados
2. Botón ⋮ (Acción) → **Exportar Notas de Crédito a Excel**
3. Clic en **Generar Excel**
4. Clic en **Descargar**

### Filtros útiles
- **Publicadas**: Muestra solo NCs confirmadas (activo por defecto)
- **Mes Actual**: NCs del mes en curso
- **Año Actual**: NCs del año en curso
- **Búsqueda**: Buscar por cliente, número, factura o motivo

## 🔄 Actualización del Módulo

Si se modifica el código del módulo:

```bash
# Reiniciar Odoo con actualización
odoo-bin -c /etc/odoo.conf -d your_database -u sng_credit_note_report

# O desde la interfaz
Aplicaciones → Buscar "SNG Credit Note Report" → Actualizar
```

## 📞 Soporte

Ver el archivo [README.md](README.md) para documentación completa y troubleshooting avanzado.

---

**✅ ¡Instalación completa!** El módulo está listo para usar.
