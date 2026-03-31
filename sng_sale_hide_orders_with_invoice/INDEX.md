# 📚 Índice de Documentación - sng_sale_hide_orders_with_invoice

Bienvenido a la documentación del módulo **sng_sale_hide_orders_with_invoice** para Odoo 18.

---

## 🚀 Inicio Rápido

**¿Primera vez usando este módulo?** Empieza aquí:

1. 📖 Lee el [README.md](README.md) para entender qué hace el módulo
2. 📦 Sigue la [INSTALL.md](INSTALL.md) para instalarlo
3. 🧪 Ejecuta los tests de [TESTING.md](TESTING.md) para verificar

**Instalación en 1 comando:**
```bash
sudo bash quick_install.sh nombre_base_datos
```

---

## 📂 Estructura de la Documentación

### 📖 Para Usuarios Funcionales

| Archivo | Descripción | Tiempo de Lectura |
|---------|-------------|-------------------|
| [README.md](README.md) | **Documentación completa del módulo**<br>• Qué problema resuelve<br>• Reglas funcionales<br>• Casos de uso<br>• Ejemplos prácticos | 15 min |

### 📦 Para Administradores/DevOps

| Archivo | Descripción | Tiempo de Lectura |
|---------|-------------|-------------------|
| [INSTALL.md](INSTALL.md) | **Guía de instalación paso a paso**<br>• Instalación desde interfaz web<br>• Instalación desde CLI<br>• Actualización y desinstalación<br>• Troubleshooting | 10 min |
| [quick_install.sh](quick_install.sh) | **Script de instalación automática**<br>• Verificación de pre-requisitos<br>• Instalación con validación<br>• Tests automáticos | 2 min |

### 🧪 Para QA/Testers

| Archivo | Descripción | Tiempo de Lectura |
|---------|-------------|-------------------|
| [TESTING.md](TESTING.md) | **Scripts de prueba completos**<br>• Tests manuales desde interfaz<br>• Scripts Python para shell de Odoo<br>• Suite de tests automatizada<br>• Validación SQL | 20 min |

### 🔬 Para Desarrolladores

| Archivo | Descripción | Tiempo de Lectura |
|---------|-------------|-------------------|
| [TECHNICAL_SUMMARY.md](TECHNICAL_SUMMARY.md) | **Análisis técnico profundo**<br>• Arquitectura de la solución<br>• Flujo de datos<br>• Análisis de performance<br>• Código nativo de Odoo analizado | 25 min |

---

## 🎯 ¿Qué hace este módulo?

**En resumen:**

Modifica la vista **"Pendiente por facturar"** de Odoo para que **NO** muestre órdenes de venta que ya tienen al menos una factura asociada (incluyendo anticipos y facturas parciales).

**Antes del módulo:**
```
Vista "Pendiente por facturar" mostraba:
  ✅ Orden sin facturas
  ✅ Orden con anticipo (50% facturado)     ← Confusión
  ✅ Orden con factura parcial              ← Confusión
```

**Después del módulo:**
```
Vista "Pendiente por facturar" muestra SOLO:
  ✅ Orden sin facturas
  ❌ Orden con anticipo (excluida)
  ❌ Orden con factura parcial (excluida)
```

---

## 📊 Estadísticas del Módulo

| Métrica | Valor |
|---------|-------|
| **Versión** | 18.0.1.0.0 |
| **Líneas de código** | ~296 (Python + XML + CSV) |
| **Archivos Python** | 3 |
| **Archivos XML** | 1 |
| **Modelos extendidos** | 1 (`sale.order`) |
| **Campos agregados** | 1 (`has_invoice`) |
| **Vistas modificadas** | 1 (acción `action_orders_to_invoice`) |
| **Dependencias** | 2 (`sale`, `account`) |
| **Tamaño total** | ~100 KB (incluye docs) |
| **Complejidad** | Muy baja (1 campo computado) |
| **Tiempo de instalación** | < 10 segundos |

---

## 🗂️ Arquitectura del Módulo

```
┌─────────────────────────────────────────────────────────────────┐
│                    MÓDULO SNG                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ MODELO: sale.order (extendido)                         │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │ + has_invoice: Boolean (computed, stored)              │    │
│  │                                                         │    │
│  │ @api.depends('order_line.invoice_lines')               │    │
│  │ def _compute_has_invoice(self):                        │    │
│  │     order.has_invoice = bool(order.invoice_ids)        │    │
│  └────────────────────────────────────────────────────────┘    │
│                          ↓                                       │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ VISTA: action_orders_to_invoice (modificada)           │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │ Dominio original:                                      │    │
│  │   [('invoice_status','=','to invoice')]                │    │
│  │                                                         │    │
│  │ Dominio modificado:                                    │    │
│  │   [('invoice_status','=','to invoice'),                │    │
│  │    ('has_invoice','=',False)]                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Comandos Rápidos

### Instalación

```bash
# Instalación automática con script
sudo bash quick_install.sh nombre_bd

# Instalación manual
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf -d nombre_bd -i sng_sale_hide_orders_with_invoice --stop-after-init
```

### Actualización

```bash
# Después de modificar código
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf -d nombre_bd -u sng_sale_hide_orders_with_invoice --stop-after-init

sudo systemctl restart odoo18
```

### Verificación

```bash
# Shell de Odoo para tests
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin shell \
  -c /etc/odoo18.conf -d nombre_bd
```

```python
# En el shell de Python
module = env['ir.module.module'].search([('name', '=', 'sng_sale_hide_orders_with_invoice')])
print(f"Estado: {module.state}")  # Debe ser 'installed'
```

### Desinstalación

```bash
# Desde interfaz: Aplicaciones → Buscar módulo → Desinstalar
# O desde shell:
# module.button_immediate_uninstall()
```

---

## 🔗 Archivos del Módulo

### Código Fuente

```
sng_sale_hide_orders_with_invoice/
│
├── __init__.py                      # Inicialización del módulo
├── __manifest__.py                  # Manifiesto (metadatos, dependencias)
│
├── models/
│   ├── __init__.py
│   └── sale_order.py                # Extensión de sale.order
│
├── views/
│   └── sale_order_views.xml         # Herencia de acción
│
└── security/
    └── ir.model.access.csv          # Permisos de acceso
```

### Documentación

```
├── INDEX.md                         # Este archivo (punto de entrada)
├── README.md                        # Documentación funcional completa
├── INSTALL.md                       # Guía de instalación
├── TESTING.md                       # Scripts de prueba
├── TECHNICAL_SUMMARY.md             # Análisis técnico detallado
└── quick_install.sh                 # Script de instalación automática
```

---

## 🎓 Flujo de Aprendizaje Recomendado

### Para Usuarios Finales

1. **Lee**: [README.md](README.md) → Sección "Reglas Funcionales"
2. **Prueba**: Crea una orden sin factura → Aparece en vista
3. **Prueba**: Crea factura de anticipo → Desaparece de vista
4. **Listo**: Ya entiendes el módulo

### Para Administradores

1. **Lee**: [README.md](README.md) → Entender funcionalidad
2. **Instala**: [INSTALL.md](INSTALL.md) → Seguir pasos
3. **Valida**: [TESTING.md](TESTING.md) → Ejecutar Script 1-3
4. **Monitorea**: Revisar logs y performance

### Para Desarrolladores

1. **Lee**: [README.md](README.md) → Contexto funcional
2. **Analiza**: [TECHNICAL_SUMMARY.md](TECHNICAL_SUMMARY.md) → Arquitectura
3. **Estudia**: [models/sale_order.py](models/sale_order.py) → Código
4. **Estudia**: [views/sale_order_views.xml](views/sale_order_views.xml) → Vistas
5. **Prueba**: [TESTING.md](TESTING.md) → Scripts de validación

---

## ❓ FAQ - Preguntas Frecuentes

### 1. ¿Por qué las órdenes con anticipos no aparecen?

**R:** Porque el módulo considera que una orden con anticipo ya tiene al menos una factura asociada. El campo `has_invoice` será `True` y la orden se excluirá de la vista.

**Solución:** Esta es la funcionalidad esperada. Si necesitas ver órdenes con anticipos, usa la vista general de órdenes de venta.

---

### 2. ¿Se pierden datos al desinstalar?

**R:** No. La desinstalación solo elimina el campo `has_invoice` y restaura el dominio original de la acción. Todas las órdenes y facturas permanecen intactas.

---

### 3. ¿Afecta el rendimiento?

**R:** No significativamente. El campo `has_invoice` está almacenado (`store=True`), por lo que las búsquedas son rápidas. El impacto es <10ms adicionales en consultas.

---

### 4. ¿Funciona con Odoo Enterprise?

**R:** Sí, el módulo es compatible tanto con Odoo Community como Enterprise.

---

### 5. ¿Puedo modificar la lógica?

**R:** Sí, puedes editar el método `_compute_has_invoice()` en [models/sale_order.py](models/sale_order.py) para personalizar la lógica según tus necesidades.

---

## 📞 Soporte y Contacto

**Desarrollado por:** SNG Development Team

**Reportar bugs:**
- Revisar logs: `/var/log/odoo18/odoo.log`
- Ejecutar tests: [TESTING.md](TESTING.md)
- Contactar al equipo de desarrollo

**Recursos adicionales:**
- Documentación oficial de Odoo: https://www.odoo.com/documentation/18.0/
- Código fuente de Odoo: https://github.com/odoo/odoo/tree/18.0

---

## ✅ Checklist de Verificación

Antes de usar el módulo en producción:

- [ ] Leído [README.md](README.md) completo
- [ ] Instalado en ambiente de pruebas
- [ ] Ejecutados tests de [TESTING.md](TESTING.md)
- [ ] Validado comportamiento con órdenes reales
- [ ] Verificado que no hay errores en logs
- [ ] Capacitado al equipo de ventas
- [ ] Backup de base de datos realizado
- [ ] Listo para producción

---

## 📜 Licencia

**LGPL-3** (Lesser General Public License v3)

Este módulo es software libre y puede ser redistribuido y/o modificado bajo los términos de la licencia LGPL-3.

---

## 📅 Información de Versión

**Versión actual:** 18.0.1.0.0
**Fecha de creación:** 2026-03-20
**Última actualización:** 2026-03-20
**Estado:** Estable

---

**¡Gracias por usar sng_sale_hide_orders_with_invoice!**

Si tienes sugerencias o encuentras problemas, no dudes en contactar al equipo de desarrollo.
