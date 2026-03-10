# Payment Report

## Descripción

Módulo de Odoo 18 que proporciona un reporte completo de pagos de clientes con información detallada de las facturas asociadas.

## Características

### Información mostrada:
- **Cliente**: Nombre del cliente que realizó el pago
- **Fecha de Pago**: Cuándo se recibió el pago
- **Referencia**: Número de referencia del pago
- **Monto Pagado**: Monto del pago recibido
- **Estado Reconciliado**: Indica si el pago está vinculado a una factura
- **Factura**: Número de la factura a la que se aplicó el pago (si aplica)
- **Fecha de Factura**: Fecha de emisión de la factura (si aplica)
- **Monto sin Impuestos**: Monto de la factura sin impuestos (si aplica)
- **Días para Pago**: Días transcurridos desde la emisión de la factura hasta el pago (si aplica)

### Vistas disponibles:
1. **Vista Lista**: Detalle de todos los pagos
2. **Vista Pivot**: Análisis multidimensional con totales y subtotales
3. **Vista Gráfico**: Visualización gráfica de los datos

### Filtros predefinidos:
- Este Mes
- Mes Anterior
- Este Año
- Pago Rápido (≤ 30 días)
- Pago Normal (31-60 días)
- Pago Lento (> 60 días)
- Reconciliados
- No Reconciliados

### Agrupaciones:
- Por Cliente
- Por Fecha de Pago
- Por Mes de Pago
- Por Estado de Reconciliación
- Por Compañía

## Instalación

1. Copiar el módulo en la carpeta de addons personalizados
2. Actualizar la lista de módulos en Odoo
3. Buscar "Payment Report"
4. Instalar el módulo

## Uso

Una vez instalado, el reporte estará disponible en:

**Contabilidad → Reportes → Reporte de Pagos**

## Autor

SNG

## Licencia

LGPL-3
