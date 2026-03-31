# 📦 Guía de Instalación - sng_sale_hide_orders_with_invoice

Esta guía proporciona instrucciones paso a paso para instalar el módulo en Odoo 18.

---

## ✅ Pre-requisitos

Antes de instalar, verificar:

- ✅ Odoo 18 Community o Enterprise instalado y funcionando
- ✅ Módulo `sale` instalado
- ✅ Módulo `account` instalado
- ✅ Acceso SSH al servidor (si es instalación en servidor)
- ✅ Permisos de administrador en Odoo
- ✅ Backup de la base de datos (recomendado)

---

## 🚀 Método 1: Instalación desde Interfaz Web (Recomendado)

### Paso 1: Copiar el Módulo

El módulo debe estar en el directorio de addons custom de Odoo:

```bash
# Verificar que el módulo está en la ubicación correcta
ls -la /opt/odoo18/odoo18-custom-addons/sng_sale_hide_orders_with_invoice/

# Debería mostrar:
# __init__.py
# __manifest__.py
# README.md
# INSTALL.md
# TESTING.md
# models/
# views/
# security/
```

### Paso 2: Reiniciar Odoo (si es necesario)

Si acabas de copiar los archivos:

```bash
# Para sistemas con systemd
sudo systemctl restart odoo18

# Para instalaciones manuales
# Detener proceso actual y reiniciar con tu configuración
```

### Paso 3: Activar Modo Desarrollador

1. Ir a **Configuración** (Settings)
2. En la parte inferior, hacer clic en **Activar modo desarrollador**
3. Esperar a que se recargue la página

### Paso 4: Actualizar Lista de Aplicaciones

1. Ir a **Aplicaciones** (Apps)
2. Hacer clic en el menú superior derecho (⋮)
3. Seleccionar **Actualizar lista de aplicaciones**
4. Confirmar la actualización
5. Esperar a que complete (puede tomar 10-30 segundos)

### Paso 5: Buscar e Instalar el Módulo

1. En **Aplicaciones**, quitar el filtro "Aplicaciones" de la barra de búsqueda
2. Buscar: `sng_sale_hide_orders_with_invoice`
3. Debería aparecer el módulo con el título:
   **"SNG - Ocultar Órdenes con Facturas en Vista 'Pendiente por Facturar'"**
4. Hacer clic en **Instalar**
5. Esperar a que complete la instalación (normalmente < 10 segundos)

### Paso 6: Verificar Instalación

1. Ir a **Ventas → Órdenes → Pendiente por facturar**
2. La vista debería mostrar solo órdenes SIN facturas asociadas
3. Verificar que el módulo está instalado:
   - Ir a **Aplicaciones**
   - Buscar el módulo
   - Debería mostrar estado "Instalado" con opción de **Desinstalar**

---

## 🔧 Método 2: Instalación desde Línea de Comandos

### Opción A: Instalar en Base de Datos Específica

```bash
# Sintaxis básica
/opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d nombre_base_datos \
  -i sng_sale_hide_orders_with_invoice \
  --stop-after-init

# Ejemplo real
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d produccion_db \
  -i sng_sale_hide_orders_with_invoice \
  --stop-after-init
```

**Explicación de parámetros:**
- `-c /etc/odoo18.conf`: Archivo de configuración de Odoo
- `-d nombre_base_datos`: Nombre de la base de datos donde instalar
- `-i sng_sale_hide_orders_with_invoice`: Módulo a instalar
- `--stop-after-init`: Detener Odoo después de instalar (no queda en ejecución)

### Opción B: Instalar desde Shell de Odoo

```bash
# Acceder al shell
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin shell \
  -c /etc/odoo18.conf \
  -d nombre_base_datos
```

Luego ejecutar en el shell de Python:

```python
# Buscar el módulo
module = env['ir.module.module'].search([
    ('name', '=', 'sng_sale_hide_orders_with_invoice')
])

if not module:
    print("❌ Módulo no encontrado. Verificar que está en addons_path.")
else:
    print(f"✅ Módulo encontrado: {module.name}")
    print(f"   Estado actual: {module.state}")

    if module.state == 'installed':
        print("   ⚠️  Ya está instalado")
    else:
        print("   Instalando...")
        module.button_immediate_install()
        print("   ✅ Instalado correctamente")

# Guardar cambios
env.cr.commit()
```

---

## 🔄 Actualizar el Módulo (Después de Modificaciones)

Si realizas cambios en el código del módulo:

### Desde Interfaz Web

1. Ir a **Aplicaciones**
2. Buscar `sng_sale_hide_orders_with_invoice`
3. Hacer clic en **Actualizar**
4. Esperar a que complete

### Desde Línea de Comandos

```bash
# Actualizar módulo
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d nombre_base_datos \
  -u sng_sale_hide_orders_with_invoice \
  --stop-after-init

# Luego reiniciar Odoo
sudo systemctl restart odoo18
```

---

## 🗑️ Desinstalar el Módulo

### Desde Interfaz Web

1. Ir a **Aplicaciones**
2. Buscar `sng_sale_hide_orders_with_invoice`
3. Hacer clic en **Desinstalar**
4. Confirmar la desinstalación

**Nota:** Al desinstalar:
- El campo `has_invoice` se eliminará de la base de datos
- La acción `action_orders_to_invoice` volverá a su dominio original
- No se pierden datos de órdenes ni facturas

### Desde Línea de Comandos

```bash
# Desinstalar desde shell
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo18/odoo-bin shell \
  -c /etc/odoo18.conf \
  -d nombre_base_datos
```

```python
# En shell de Python
module = env['ir.module.module'].search([
    ('name', '=', 'sng_sale_hide_orders_with_invoice')
])

if module.state == 'installed':
    module.button_immediate_uninstall()
    print("✅ Módulo desinstalado")

env.cr.commit()
```

---

## 🔍 Verificación Post-Instalación

### Test Rápido desde Interfaz

1. **Crear una orden sin factura:**
   - Ir a **Ventas → Órdenes → Crear**
   - Agregar cliente y productos
   - Confirmar la orden
   - **NO** crear factura
   - Ir a **Ventas → Órdenes → Pendiente por facturar**
   - ✅ La orden DEBE aparecer

2. **Crear una orden con factura:**
   - Crear otra orden y confirmarla
   - Hacer clic en **Crear Factura**
   - Validar la factura
   - Ir a **Ventas → Órdenes → Pendiente por facturar**
   - ❌ La orden NO debe aparecer

### Test desde Shell de Odoo

```python
# Verificar instalación
module = env['ir.module.module'].search([
    ('name', '=', 'sng_sale_hide_orders_with_invoice')
])
print(f"Estado: {module.state}")  # Debe ser 'installed'

# Verificar campo has_invoice
field = env['ir.model.fields'].search([
    ('model', '=', 'sale.order'),
    ('name', '=', 'has_invoice')
])
print(f"Campo existe: {bool(field)}")  # Debe ser True

# Verificar dominio de acción
action = env.ref('sale.action_orders_to_invoice')
print(f"Dominio: {action.domain}")  # Debe incluir ('has_invoice','=',False)

# Contar órdenes pendientes
orders = env['sale.order'].search([
    ('invoice_status', '=', 'to invoice'),
    ('has_invoice', '=', False)
])
print(f"Órdenes pendientes sin facturas: {len(orders)}")
```

---

## 🐛 Solución de Problemas

### Problema 1: Módulo no aparece en lista de aplicaciones

**Causas posibles:**
- El módulo no está en el `addons_path` de Odoo
- Falta actualizar lista de aplicaciones
- Error de sintaxis en `__manifest__.py`

**Solución:**
```bash
# Verificar addons_path
grep addons_path /etc/odoo18.conf

# Debe incluir: /opt/odoo18/odoo18-custom-addons

# Verificar que el módulo está allí
ls -la /opt/odoo18/odoo18-custom-addons/sng_sale_hide_orders_with_invoice/

# Verificar sintaxis del manifest
python3 -m py_compile /opt/odoo18/odoo18-custom-addons/sng_sale_hide_orders_with_invoice/__manifest__.py

# Reiniciar Odoo
sudo systemctl restart odoo18

# Actualizar lista de aplicaciones desde interfaz
```

### Problema 2: Error al instalar

**Error típico:**
```
ParseError: Field 'has_invoice' does not exist
```

**Solución:**
```bash
# Verificar que los archivos están completos
ls -la /opt/odoo18/odoo18-custom-addons/sng_sale_hide_orders_with_invoice/models/

# Debe mostrar:
# __init__.py
# sale_order.py

# Verificar sintaxis Python
python3 -m py_compile /opt/odoo18/odoo18-custom-addons/sng_sale_hide_orders_with_invoice/models/sale_order.py

# Reiniciar Odoo
sudo systemctl restart odoo18

# Intentar instalar nuevamente
```

### Problema 3: Módulo instalado pero vista no cambia

**Verificaciones:**

```python
# Desde shell de Odoo
# 1. Verificar que el módulo está instalado
module = env['ir.module.module'].search([
    ('name', '=', 'sng_sale_hide_orders_with_invoice')
])
print(f"Estado: {module.state}")

# 2. Verificar dominio
action = env.ref('sale.action_orders_to_invoice')
print(f"Dominio: {action.domain}")

# 3. Forzar actualización de la acción
action.domain = "[('invoice_status','=','to invoice'), ('has_invoice','=',False)]"
env.cr.commit()

# 4. Limpiar caché del navegador
# CTRL + F5 en el navegador
```

### Problema 4: Campo has_invoice siempre es False

**Causa:** El campo no se está calculando correctamente

**Solución:**
```python
# Forzar recálculo
orders = env['sale.order'].search([])
orders._compute_has_invoice()
env.cr.commit()

# Verificar un caso específico
order = env['sale.order'].browse(ID_ORDEN)
print(f"Orden: {order.name}")
print(f"invoice_count: {order.invoice_count}")
print(f"invoice_ids: {order.invoice_ids}")
print(f"has_invoice: {order.has_invoice}")
```

---

## 📋 Checklist de Instalación

Marcar cada paso completado:

- [ ] Módulo copiado en directorio correcto
- [ ] Permisos de archivos correctos (`odoo18:odoo18`)
- [ ] Odoo reiniciado (si fue necesario)
- [ ] Modo desarrollador activado
- [ ] Lista de aplicaciones actualizada
- [ ] Módulo buscado y encontrado
- [ ] Módulo instalado sin errores
- [ ] Campo `has_invoice` existe
- [ ] Acción modificada correctamente
- [ ] Vista "Pendiente por facturar" funciona
- [ ] Tests manuales completados
- [ ] Sin errores en logs de Odoo

---

## 📞 Soporte

Si encuentras problemas durante la instalación:

1. Revisar logs de Odoo: `/var/log/odoo18/odoo.log`
2. Ejecutar Odoo en modo debug: `--log-level=debug`
3. Verificar script de tests en `TESTING.md`
4. Contactar al equipo de desarrollo de SNG

---

## 🎯 Próximos Pasos

Después de instalar:

1. Leer el **README.md** para entender la funcionalidad completa
2. Ejecutar tests del **TESTING.md** para validar
3. Probar con órdenes reales en ambiente de staging
4. Desplegar en producción con confianza

---

**Autor:** SNG Development Team
**Versión del documento:** 1.0.0
**Última actualización:** 2026-03-20
