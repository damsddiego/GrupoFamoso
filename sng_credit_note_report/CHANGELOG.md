# Changelog - SNG Credit Note Report

## Version 18.0.1.0.0 (2026-03-05)

### Inicial Release

**Características:**
- ✅ Reporte completo de Notas de Crédito
- ✅ Facturas relacionadas via reconciliaciones contables
- ✅ Exportación a Excel (XLSX)
- ✅ Filtros avanzados y búsqueda
- ✅ SQL VIEW optimizada con CTE
- ✅ Soporte multi-compañía
- ✅ Documentación completa

**Notas técnicas:**
- Usa `<list>` en lugar de `<tree>` (cambio en Odoo 18)
- Vista SQL con CTE para máximo rendimiento
- Sin N+1 queries

**Compatibilidad:**
- Odoo 18 Community Edition ✓
- Odoo 18 Enterprise ✓

**Dependencias:**
- Python: xlsxwriter
- Odoo: account

---

## Cambios importantes en Odoo 18

### Vista List (anteriormente Tree)

En Odoo 18, el tag XML para vistas de lista cambió de `<tree>` a `<list>`.

**Antes (Odoo 17 y anteriores):**
```xml
<tree string="Mi Lista">
    <field name="name"/>
</tree>
```

**Ahora (Odoo 18):**
```xml
<list string="Mi Lista">
    <field name="name"/>
</list>
```

**Impacto en este módulo:**
- ✅ Todas las vistas usan `<list>`
- ✅ El `view_mode` en acciones usa `list`
- ⚠️ Si portas a Odoo 17-, cambia `<list>` → `<tree>`

---

## Roadmap / Mejoras Futuras

### Versión 1.1.0 (Planificada)
- [ ] Vista pivot para análisis
- [ ] Vista graph con métricas visuales
- [ ] Drill-down a NC y facturas desde el reporte

### Versión 1.2.0 (Planificada)
- [ ] Exportación a PDF
- [ ] Envío automático por email
- [ ] Dashboard con KPIs

### Versión 2.0.0 (Planificada)
- [ ] Reporte de Notas de Débito
- [ ] Comparativas período a período
- [ ] Filtros guardados personalizados

---

**Mantenido por:** SNG
**Licencia:** LGPL-3
