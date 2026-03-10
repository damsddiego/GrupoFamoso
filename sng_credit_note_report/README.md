# SNG Credit Note Report

## Descripción

Módulo de reporte de Notas de Crédito para Odoo 18 Community Edition que proporciona una vista completa de todas las notas de crédito de clientes con información detallada y capacidad de exportación a Excel.

## Características

### 📊 Reporte Completo de Notas de Crédito

- **Información del Cliente:**
  - ID único del cliente (partner.unique_id)
  - Nombre del cliente

- **Información de la Nota de Crédito:**
  - Número de documento
  - Fecha (invoice_date o date si no hay fecha de factura)
  - Monto total
  - Motivo/referencia

- **Facturas Relacionadas:**
  - Detecta automáticamente las facturas reconciliadas con cada nota de crédito
  - Utiliza las reconciliaciones contables (account.partial.reconcile)
  - Muestra todos los números de factura relacionados
  - Sin duplicados y ordenados alfabéticamente

### 🔍 Filtros Avanzados

- Filtro por estado (Publicadas/Borrador/Canceladas)
- Filtro por rango de fechas (Mes actual, Año actual, personalizado)
- Filtro por cliente
- Filtro por compañía (multi-compañía)
- Búsqueda por número de NC, factura relacionada o motivo
- Agrupación por cliente, estado, fecha o compañía

### 📥 Exportación a Excel (XLSX)

- Exportación directa desde la vista de lista
- Respeta filtros y selecciones activas
- Formato profesional con:
  - Encabezados destacados
  - Fechas formateadas correctamente
  - Montos con formato numérico (2 decimales)
  - Columnas auto-ajustadas
  - Primera fila congelada
- Nombre de archivo con timestamp

### ⚡ Alto Rendimiento

- Implementado con SQL VIEW para máxima velocidad
- Consulta optimizada con CTE (Common Table Expression)
- Evita N+1 queries al resolver facturas relacionadas
- Sin impacto en la base de datos (vista de solo lectura)

## Instalación

### Requisitos Previos

1. **Odoo 18 Community Edition**
2. **Módulo `account` instalado** (viene por defecto)
3. **Librería Python xlsxwriter** (para exportación Excel):
   ```bash
   pip install xlsxwriter
   ```

### Pasos de Instalación

1. **Copiar el módulo:**
   ```bash
   cp -r sng_credit_note_report /path/to/odoo/addons/
   ```

2. **Actualizar la lista de aplicaciones:**
   - Ir a **Aplicaciones** en Odoo
   - Hacer clic en el menú (☰) y seleccionar **Actualizar Lista de Aplicaciones**
   - Confirmar la actualización

3. **Instalar el módulo:**
   - Buscar "SNG Credit Note Report"
   - Hacer clic en **Instalar**

4. **Verificar instalación:**
   - Ir a **Contabilidad → Reportes**
   - Debería aparecer el menú **Notas de Crédito (SNG)**

## Uso

### Acceder al Reporte

1. Ir a **Contabilidad → Reportes → Notas de Crédito (SNG)**
2. Por defecto, muestra solo notas de crédito publicadas

### Aplicar Filtros

- **Filtros rápidos:** Usar los botones en la barra superior
  - "Publicadas" (activo por defecto)
  - "Borrador"
  - "Canceladas"
  - "Mes Actual"
  - "Año Actual"

- **Búsqueda:** Escribir en la barra de búsqueda
  - Busca en: nombre de cliente, ID cliente, número de NC, motivo, facturas relacionadas

- **Filtros avanzados:** Hacer clic en "Filtros" para opciones avanzadas

- **Agrupación:** Hacer clic en "Agrupar por" para organizar datos

### Exportar a Excel

**Opción 1: Exportar registros filtrados**
1. Aplicar los filtros deseados
2. Hacer clic en el botón "⋮" (Acción) en la parte superior
3. Seleccionar "Exportar Notas de Crédito a Excel"
4. Hacer clic en "Generar Excel"
5. Descargar el archivo generado

**Opción 2: Exportar registros seleccionados**
1. Marcar los checkboxes de los registros específicos
2. Hacer clic en el botón "⋮" (Acción)
3. Seleccionar "Exportar Notas de Crédito a Excel"
4. Solo se exportarán los registros seleccionados

**Opción 3: Exportación estándar de Odoo**
- Usar el menú "Favoritos → Exportar" para exportación CSV/XLSX básica

## Estructura Técnica

### Arquitectura del Módulo

```
sng_credit_note_report/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   └── sng_credit_note_report.py      # Modelo SQL VIEW
├── views/
│   └── sng_credit_note_report_views.xml  # Vistas tree, search, menu
├── wizard/
│   ├── __init__.py
│   ├── sng_credit_note_export_wizard.py        # Lógica de exportación XLSX
│   └── sng_credit_note_export_wizard_views.xml # Vista del wizard
└── security/
    └── ir.model.access.csv            # Permisos de acceso
```

### Modelo: `sng.credit.note.report`

**Tipo:** SQL VIEW (no editable, solo lectura)

**Campos principales:**
- `partner_unique_id`: ID único del cliente
- `partner_name`: Nombre del cliente
- `credit_note_number`: Número de la nota de crédito
- `credit_note_date`: Fecha de la NC
- `credit_note_amount`: Monto total
- `reason_ref`: Motivo/referencia
- `related_invoices`: Facturas reconciliadas (concatenadas)
- `state`: Estado (draft/posted/cancel)
- `company_id`: Compañía

### Lógica de Facturas Relacionadas

El módulo utiliza un enfoque basado en **reconciliaciones contables** para determinar las facturas relacionadas:

#### ¿Por qué no usar `invoice_origin`?

- El campo `invoice_origin` es solo un texto de referencia
- No siempre refleja las reconciliaciones reales
- Puede estar vacío o desactualizado
- No maneja múltiples facturas correctamente

#### Método Implementado: Reconciliaciones (account.partial.reconcile)

1. **Se parte de las líneas contables** de la nota de crédito (`account.move.line`)

2. **Se buscan reconciliaciones parciales:**
   - `matched_debit_ids`: Cuando la NC es el lado crédito
   - `matched_credit_ids`: Cuando la NC es el lado débito

3. **Se obtienen las líneas reconciliadas del lado opuesto**

4. **Se identifican los account.move relacionados:**
   - Solo se incluyen facturas de cliente (`move_type='out_invoice'`)
   - Se excluyen otros tipos de documentos

5. **Se concatenan los números de factura:**
   - Sin duplicados
   - Ordenados alfabéticamente
   - Separados por comas

#### Implementación SQL (CTE)

```sql
WITH credit_note_invoices AS (
    SELECT
        cn_line.move_id AS credit_note_id,
        STRING_AGG(DISTINCT inv.name, ', ' ORDER BY inv.name) AS related_invoice_numbers
    FROM account_move_line cn_line
    LEFT JOIN account_partial_reconcile apr_credit
        ON apr_credit.credit_move_id = cn_line.id
    LEFT JOIN account_move_line inv_line_from_credit
        ON inv_line_from_credit.id = apr_credit.debit_move_id
    -- (más joins para ambos casos)
    GROUP BY cn_line.move_id
)
```

### Seguridad

El módulo respeta los grupos de contabilidad de Odoo:

- **account.group_account_readonly**: Acceso de solo lectura al reporte
- **account.group_account_invoice**: Acceso completo al reporte y exportación
- **account.group_account_manager**: Acceso completo a todas las funciones

### Multi-Compañía

- El reporte respeta automáticamente las reglas de acceso por compañía
- Los filtros incluyen selector de compañía (si aplica)
- Solo muestra datos de las compañías autorizadas para el usuario

## Dependencias

### Módulos de Odoo
- `account` (Contabilidad)

### Librerías Python
- `xlsxwriter` (para exportación Excel)

## Notas de Implementación

### Campo `partner.unique_id`

El módulo asume que existe un campo `unique_id` en el modelo `res.partner`.

**Si el campo no existe en tu instalación:**

1. **Opción A:** Crear el campo en `res.partner` mediante otro módulo
2. **Opción B:** Modificar el modelo para usar otro campo (ej: `vat`, `ref`)

Editar [sng_credit_note_report.py](models/sng_credit_note_report.py:68):
```python
# Cambiar:
rp.unique_id AS partner_unique_id,

# Por uno de estos:
rp.vat AS partner_unique_id,         # NIF/CIF
rp.ref AS partner_unique_id,         # Referencia interna
CAST(rp.id AS VARCHAR) AS partner_unique_id,  # ID numérico
```

### Rendimiento

- **SQL VIEW:** La vista se regenera automáticamente, no almacena datos
- **CTE optimizado:** Resuelve todas las facturas relacionadas en una sola consulta
- **Sin N+1:** No hay loops por cada registro
- **Índices:** Utiliza índices nativos de Odoo en las tablas base

### Compatibilidad

- **Odoo 18 Community Edition:** ✅ Totalmente compatible
- **Odoo 18 Enterprise:** ✅ Compatible (no requiere funciones enterprise)
- **Odoo 17 y anteriores:** ⚠️ Requiere adaptación (cambios en API de vistas)

## Mantenimiento

### Actualización de la Vista SQL

Si se modifica la lógica SQL en `models/sng_credit_note_report.py`:

1. Actualizar el módulo:
   ```bash
   odoo-bin -u sng_credit_note_report -d your_database
   ```

2. O desde la interfaz:
   - **Aplicaciones → Buscar "SNG Credit Note Report" → Actualizar**

### Logs y Debugging

Si la vista no muestra datos:

1. **Verificar que existen notas de crédito:**
   ```sql
   SELECT COUNT(*) FROM account_move WHERE move_type = 'out_refund';
   ```

2. **Verificar la vista SQL:**
   ```sql
   SELECT * FROM sng_credit_note_report LIMIT 10;
   ```

3. **Ver logs de Odoo:**
   ```bash
   tail -f /var/log/odoo/odoo-server.log
   ```

## Troubleshooting

### Error: "xlsxwriter module not found"

**Solución:**
```bash
pip install xlsxwriter
# O con pip3
pip3 install xlsxwriter
```

Luego reiniciar Odoo.

### No aparece el menú en Contabilidad

**Verificar:**
1. El usuario tiene permisos de contabilidad (`account.group_account_readonly` o superior)
2. El módulo está correctamente instalado (no solo cargado)
3. Refrescar el navegador (Ctrl+Shift+R)

### La columna "Facturas Relacionadas" está vacía

**Posibles causas:**
1. Las notas de crédito no están reconciliadas con facturas
2. Las reconciliaciones se hicieron manualmente sin pasar por el asistente
3. Se usó el campo `invoice_origin` en lugar de reconciliaciones reales

**Verificar reconciliaciones:**
```sql
SELECT
    am.name AS credit_note,
    COUNT(apr.id) AS reconciliations
FROM account_move am
JOIN account_move_line aml ON aml.move_id = am.id
LEFT JOIN account_partial_reconcile apr ON apr.credit_move_id = aml.id OR apr.debit_move_id = aml.id
WHERE am.move_type = 'out_refund'
GROUP BY am.id, am.name;
```

### Rendimiento lento

Si el reporte es lento con muchos registros:

1. **Verificar índices** en `account_move_line`, `account_partial_reconcile`
2. **Añadir límite temporal** en la vista mientras se optimiza
3. **Considerar materializar la vista** si el volumen es muy grande (>100k registros)

## Soporte y Contribuciones

Para reportar bugs o solicitar funcionalidades, contactar al equipo de desarrollo SNG.

## Licencia

LGPL-3 - Ver archivo LICENSE para más detalles.

## Autor

**SNG**

## Versión

**1.0.0** - Compatible con Odoo 18 Community Edition

---

**¡Gracias por usar SNG Credit Note Report!** 🚀
