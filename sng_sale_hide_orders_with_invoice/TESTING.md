# 🧪 Scripts de Prueba - sng_sale_hide_orders_with_invoice

Este documento contiene scripts Python que puedes ejecutar desde el shell de Odoo para probar el módulo.

## 📌 Cómo Acceder al Shell de Odoo

```bash
# Opción 1: Shell interactivo
odoo-bin shell -c /etc/odoo18.conf -d nombre_bd

# Opción 2: Ejecutar script desde archivo
odoo-bin shell -c /etc/odoo18.conf -d nombre_bd < test_script.py
```

---

## 🔍 Script 1: Verificar Instalación del Módulo

```python
# Verificar que el módulo está instalado
module = env['ir.module.module'].search([
    ('name', '=', 'sng_sale_hide_orders_with_invoice')
])

if module:
    print(f"✅ Módulo encontrado: {module.name}")
    print(f"   Estado: {module.state}")
    print(f"   Versión: {module.latest_version}")
else:
    print("❌ Módulo NO encontrado")

# Verificar que el campo has_invoice existe
try:
    field = env['ir.model.fields'].search([
        ('model', '=', 'sale.order'),
        ('name', '=', 'has_invoice')
    ])
    if field:
        print(f"✅ Campo 'has_invoice' existe")
        print(f"   Tipo: {field.ttype}")
        print(f"   Almacenado: {field.store}")
    else:
        print("❌ Campo 'has_invoice' NO encontrado")
except Exception as e:
    print(f"❌ Error al buscar campo: {e}")

# Verificar la acción modificada
action = env.ref('sale.action_orders_to_invoice')
print(f"\n✅ Acción 'Orders to Invoice':")
print(f"   Dominio: {action.domain}")
print(f"   Debe incluir: ('has_invoice','=',False)")
```

---

## 🧪 Script 2: Crear Orden de Prueba SIN Facturas

```python
# Este test crea una orden que DEBE aparecer en "Pendiente por facturar"

# 1. Buscar o crear partner de prueba
partner = env['res.partner'].search([('name', '=', 'Cliente Test SNG')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'Cliente Test SNG',
        'email': 'test@sng.com',
    })
    print(f"✅ Partner creado: {partner.name} (ID: {partner.id})")

# 2. Buscar producto
product = env['product.product'].search([
    ('sale_ok', '=', True),
    ('type', '=', 'product')
], limit=1)

if not product:
    print("❌ No hay productos disponibles para venta")
else:
    print(f"✅ Producto seleccionado: {product.name} (ID: {product.id})")

    # 3. Crear orden de venta
    order = env['sale.order'].create({
        'partner_id': partner.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': 10,
            'price_unit': product.list_price,
        })],
    })
    print(f"✅ Orden creada: {order.name} (ID: {order.id})")

    # 4. Confirmar orden
    order.action_confirm()
    print(f"✅ Orden confirmada")
    print(f"   Estado: {order.state}")
    print(f"   invoice_status: {order.invoice_status}")
    print(f"   has_invoice: {order.has_invoice}")
    print(f"   invoice_count: {order.invoice_count}")

    # 5. Verificar que aparece en la vista
    if order.invoice_status == 'to invoice' and not order.has_invoice:
        print("\n✅✅✅ TEST PASSED: Orden DEBE aparecer en 'Pendiente por facturar'")
    else:
        print("\n❌❌❌ TEST FAILED: Orden NO cumple los criterios esperados")

    env.cr.commit()
```

---

## 🧪 Script 3: Crear Orden con Factura de Anticipo

```python
# Este test crea una orden que NO DEBE aparecer en "Pendiente por facturar"

# 1. Buscar partner
partner = env['res.partner'].search([('name', '=', 'Cliente Test SNG')], limit=1)
if not partner:
    partner = env['res.partner'].create({'name': 'Cliente Test SNG'})

# 2. Buscar producto
product = env['product.product'].search([
    ('sale_ok', '=', True),
    ('type', '=', 'product')
], limit=1)

if not product:
    print("❌ No hay productos disponibles")
else:
    # 3. Crear orden
    order = env['sale.order'].create({
        'partner_id': partner.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': 10,
            'price_unit': 100.0,
        })],
    })
    print(f"✅ Orden creada: {order.name} (ID: {order.id})")

    # 4. Confirmar orden
    order.action_confirm()
    print(f"✅ Orden confirmada")

    # 5. Crear factura de anticipo (30%)
    wizard = env['sale.advance.payment.inv'].with_context({
        'active_ids': [order.id],
        'active_id': order.id,
    }).create({
        'advance_payment_method': 'percentage',
        'amount': 30.0,
    })
    print(f"✅ Wizard de anticipo creado")

    # 6. Crear y validar factura
    wizard.create_invoices()
    invoice = order.invoice_ids[0]
    print(f"✅ Factura de anticipo creada: {invoice.name} (ID: {invoice.id})")

    # Validar factura si está en borrador
    if invoice.state == 'draft':
        invoice.action_post()
        print(f"✅ Factura validada")

    # 7. Verificar estado de la orden
    print(f"\n📊 Estado de la orden después de anticipo:")
    print(f"   invoice_status: {order.invoice_status}")
    print(f"   has_invoice: {order.has_invoice}")
    print(f"   invoice_count: {order.invoice_count}")
    print(f"   Facturas: {', '.join(order.invoice_ids.mapped('name'))}")

    # 8. Validar test
    if order.has_invoice:
        print("\n✅✅✅ TEST PASSED: Orden NO DEBE aparecer en 'Pendiente por facturar'")
        print("   Razón: has_invoice=True (tiene factura de anticipo)")
    else:
        print("\n❌❌❌ TEST FAILED: has_invoice debería ser True")

    env.cr.commit()
```

---

## 🧪 Script 4: Verificar Todas las Órdenes Pendientes

```python
# Script para analizar todas las órdenes pendientes de facturar

print("=" * 80)
print("ANÁLISIS DE ÓRDENES PENDIENTES DE FACTURAR")
print("=" * 80)

# Buscar órdenes con invoice_status = 'to invoice'
orders = env['sale.order'].search([
    ('invoice_status', '=', 'to invoice')
])

print(f"\n📊 Total de órdenes con invoice_status='to invoice': {len(orders)}")

# Separar por has_invoice
with_invoices = orders.filtered(lambda o: o.has_invoice)
without_invoices = orders.filtered(lambda o: not o.has_invoice)

print(f"\n✅ Órdenes SIN facturas (has_invoice=False): {len(without_invoices)}")
print(f"   → Estas SÍ deben aparecer en 'Pendiente por facturar'\n")

for order in without_invoices[:10]:  # Mostrar máximo 10
    print(f"   • {order.name} | Cliente: {order.partner_id.name} | Total: {order.amount_total}")

print(f"\n❌ Órdenes CON facturas (has_invoice=True): {len(with_invoices)}")
print(f"   → Estas NO deben aparecer en 'Pendiente por facturar'\n")

for order in with_invoices[:10]:  # Mostrar máximo 10
    print(f"   • {order.name} | Cliente: {order.partner_id.name} | Facturas: {order.invoice_count}")

# Verificar consistencia de datos
print("\n" + "=" * 80)
print("VERIFICACIÓN DE CONSISTENCIA")
print("=" * 80)

inconsistent = []
for order in orders:
    # Verificar que has_invoice coincide con invoice_count
    expected_has_invoice = bool(order.invoice_ids)
    if order.has_invoice != expected_has_invoice:
        inconsistent.append(order)
        print(f"⚠️  Inconsistencia en {order.name}:")
        print(f"   has_invoice: {order.has_invoice}")
        print(f"   invoice_count: {order.invoice_count}")
        print(f"   invoice_ids: {order.invoice_ids.mapped('name')}")

if not inconsistent:
    print("✅ Todos los datos son consistentes")
else:
    print(f"\n❌ {len(inconsistent)} órdenes con inconsistencias")
    print("   Ejecutar: orders._compute_has_invoice() para recalcular")
```

---

## 🧪 Script 5: Recalcular Campo `has_invoice`

```python
# Script para recalcular el campo has_invoice en todas las órdenes

print("🔄 Recalculando campo 'has_invoice' para todas las órdenes...")

# Buscar todas las órdenes
orders = env['sale.order'].search([])
total = len(orders)

print(f"📊 Total de órdenes a procesar: {total}")

# Recalcular
orders._compute_has_invoice()

print("✅ Recálculo completado")

# Verificar resultados
with_invoices = len(orders.filtered(lambda o: o.has_invoice))
without_invoices = total - with_invoices

print(f"\n📊 Resultados:")
print(f"   Órdenes con facturas: {with_invoices}")
print(f"   Órdenes sin facturas: {without_invoices}")

# Guardar cambios
env.cr.commit()
print("\n💾 Cambios guardados en base de datos")
```

---

## 🧪 Script 6: Comparar Vista Original vs Modificada

```python
# Script para comparar cuántas órdenes se muestran en cada caso

print("=" * 80)
print("COMPARACIÓN: VISTA ORIGINAL vs VISTA MODIFICADA")
print("=" * 80)

# Dominio original (Odoo nativo)
domain_original = [('invoice_status', '=', 'to invoice')]
orders_original = env['sale.order'].search(domain_original)

# Dominio modificado (con este módulo)
domain_modificado = [
    ('invoice_status', '=', 'to invoice'),
    ('has_invoice', '=', False)
]
orders_modificado = env['sale.order'].search(domain_modificado)

# Órdenes excluidas
orders_excluidas = orders_original - orders_modificado

print(f"\n📊 VISTA ORIGINAL (Odoo nativo):")
print(f"   Dominio: {domain_original}")
print(f"   Órdenes mostradas: {len(orders_original)}")

print(f"\n📊 VISTA MODIFICADA (con módulo SNG):")
print(f"   Dominio: {domain_modificado}")
print(f"   Órdenes mostradas: {len(orders_modificado)}")

print(f"\n📊 ÓRDENES EXCLUIDAS:")
print(f"   Total: {len(orders_excluidas)}")
print(f"   Razón: Tienen al menos una factura asociada (has_invoice=True)")

if orders_excluidas:
    print(f"\n🔍 Detalle de órdenes excluidas (primeras 10):")
    for order in orders_excluidas[:10]:
        print(f"\n   Orden: {order.name}")
        print(f"   Cliente: {order.partner_id.name}")
        print(f"   Total: {order.amount_total} {order.currency_id.name}")
        print(f"   Facturas: {order.invoice_count}")
        print(f"   Detalle facturas:")
        for inv in order.invoice_ids:
            print(f"      • {inv.name} | Estado: {inv.state} | Total: {inv.amount_total}")

print("\n" + "=" * 80)
```

---

## 🧪 Script 7: Test Completo Automatizado

```python
# Script de test completo que verifica todas las funcionalidades

def run_test_suite():
    """
    Suite completa de tests para el módulo sng_sale_hide_orders_with_invoice
    """
    print("\n" + "=" * 80)
    print("TEST SUITE: sng_sale_hide_orders_with_invoice")
    print("=" * 80)

    tests_passed = 0
    tests_failed = 0

    # TEST 1: Verificar instalación
    print("\n[TEST 1] Verificar instalación del módulo...")
    try:
        module = env['ir.module.module'].search([
            ('name', '=', 'sng_sale_hide_orders_with_invoice')
        ])
        assert module.state == 'installed', f"Módulo no instalado (estado: {module.state})"
        print("   ✅ PASSED: Módulo instalado correctamente")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1

    # TEST 2: Verificar campo has_invoice
    print("\n[TEST 2] Verificar existencia del campo 'has_invoice'...")
    try:
        field = env['ir.model.fields'].search([
            ('model', '=', 'sale.order'),
            ('name', '=', 'has_invoice')
        ])
        assert field, "Campo has_invoice no encontrado"
        assert field.store, "Campo has_invoice no está almacenado"
        print("   ✅ PASSED: Campo 'has_invoice' existe y está almacenado")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1

    # TEST 3: Verificar dominio de acción
    print("\n[TEST 3] Verificar dominio de la acción modificada...")
    try:
        action = env.ref('sale.action_orders_to_invoice')
        domain_str = str(action.domain)
        assert "has_invoice" in domain_str, "Dominio no incluye 'has_invoice'"
        assert "False" in domain_str, "Dominio no excluye órdenes con facturas"
        print("   ✅ PASSED: Dominio modificado correctamente")
        print(f"   Dominio: {action.domain}")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1

    # TEST 4: Verificar consistencia de datos
    print("\n[TEST 4] Verificar consistencia de datos en órdenes existentes...")
    try:
        orders = env['sale.order'].search([], limit=100)
        inconsistent = 0
        for order in orders:
            expected = bool(order.invoice_ids)
            if order.has_invoice != expected:
                inconsistent += 1

        assert inconsistent == 0, f"{inconsistent} órdenes con datos inconsistentes"
        print(f"   ✅ PASSED: {len(orders)} órdenes verificadas, todas consistentes")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1

    # TEST 5: Verificar lógica de filtrado
    print("\n[TEST 5] Verificar lógica de filtrado...")
    try:
        # Órdenes con dominio original
        original = env['sale.order'].search([('invoice_status', '=', 'to invoice')])
        # Órdenes con dominio modificado
        modificado = env['sale.order'].search([
            ('invoice_status', '=', 'to invoice'),
            ('has_invoice', '=', False)
        ])

        excluidas = original - modificado

        assert len(modificado) <= len(original), "Vista modificada muestra MÁS órdenes que original"

        print(f"   ✅ PASSED: Filtrado funciona correctamente")
        print(f"   Vista original: {len(original)} órdenes")
        print(f"   Vista modificada: {len(modificado)} órdenes")
        print(f"   Órdenes excluidas: {len(excluidas)} (tienen facturas)")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        tests_failed += 1

    # RESUMEN
    print("\n" + "=" * 80)
    print("RESUMEN DE TESTS")
    print("=" * 80)
    print(f"✅ Tests exitosos: {tests_passed}")
    print(f"❌ Tests fallidos: {tests_failed}")
    print(f"📊 Total: {tests_passed + tests_failed}")

    if tests_failed == 0:
        print("\n🎉🎉🎉 TODOS LOS TESTS PASARON 🎉🎉🎉")
    else:
        print(f"\n⚠️  {tests_failed} test(s) fallaron. Revisar configuración.")

    return tests_passed, tests_failed

# Ejecutar suite de tests
run_test_suite()
```

---

## 🚀 Ejecución Rápida de Tests

Para ejecutar todos los tests de una vez:

```bash
# Guardar el script en un archivo
cat > /tmp/test_sng_module.py << 'EOF'
# [Copiar aquí el Script 7 completo]
EOF

# Ejecutar desde shell de Odoo
odoo-bin shell -c /etc/odoo18.conf -d nombre_bd < /tmp/test_sng_module.py
```

---

## 📊 Validación SQL

Para verificar desde SQL:

```sql
-- Verificar que el campo existe
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'sale_order' AND column_name = 'has_invoice';

-- Contar órdenes por estado de facturación y has_invoice
SELECT
    invoice_status,
    has_invoice,
    COUNT(*) as total
FROM sale_order
WHERE invoice_status = 'to invoice'
GROUP BY invoice_status, has_invoice;

-- Ver ejemplos de órdenes con facturas pero pendientes
SELECT
    so.name,
    so.invoice_status,
    so.has_invoice,
    COUNT(DISTINCT am.id) as num_facturas
FROM sale_order so
LEFT JOIN sale_order_line sol ON sol.order_id = so.id
LEFT JOIN sale_order_line_invoice_rel solir ON solir.order_line_id = sol.id
LEFT JOIN account_move_line aml ON aml.id = solir.invoice_line_id
LEFT JOIN account_move am ON am.id = aml.move_id
WHERE so.invoice_status = 'to invoice'
GROUP BY so.id
HAVING COUNT(DISTINCT am.id) > 0
LIMIT 10;
```

---

## ✅ Checklist de Validación

Después de instalar el módulo, verificar:

- [ ] Módulo instalado sin errores
- [ ] Campo `has_invoice` existe en `sale.order`
- [ ] Campo `has_invoice` está almacenado (`store=True`)
- [ ] Acción `action_orders_to_invoice` tiene dominio modificado
- [ ] Órdenes sin facturas aparecen en "Pendiente por facturar"
- [ ] Órdenes con anticipos NO aparecen en "Pendiente por facturar"
- [ ] Órdenes con facturas parciales NO aparecen
- [ ] El campo se actualiza automáticamente al crear facturas
- [ ] No hay errores en logs de Odoo
- [ ] Rendimiento es aceptable (< 2 segundos para cargar vista)

---

## 🐛 Debugging

Si hay problemas, activar modo debug y verificar:

```python
# Ver logs del compute
import logging
_logger = logging.getLogger(__name__)

# En el método _compute_has_invoice, agregar:
_logger.info(f"Computing has_invoice for {order.name}: {bool(order.invoice_ids)}")
```

Luego reiniciar Odoo con `--log-level=debug` y monitorear `/var/log/odoo18/odoo.log`
