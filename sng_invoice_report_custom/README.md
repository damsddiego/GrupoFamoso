# SNG Invoice Report Custom

## Descripción

Este módulo personaliza el reporte **Análisis de Facturas** de Odoo para mostrar el código del cliente concatenado con su nombre en el formato: `código - nombre`.

## Características

- Añade un nuevo campo `partner_code_name` al reporte de análisis de facturas
- Muestra el código de referencia del cliente (campo `ref`) junto con su nombre
- Si el cliente no tiene código, muestra solo el nombre
- El campo está disponible en todas las vistas: árbol, búsqueda, gráfico y pivot
- Permite buscar por código o nombre de cliente

## Formato del campo

```
[código_cliente] - [nombre_cliente]
```

Ejemplo:
```
C001 - Juan Pérez
C002 - Empresa ABC S.A.
```

Si el cliente no tiene código asignado, solo se mostrará el nombre:
```
Juan Pérez Sin Código
```

## Instalación

1. Copiar el módulo en la carpeta `addons` de Odoo
2. Actualizar la lista de aplicaciones desde el modo desarrollador
3. Buscar "SNG Invoice Report Custom"
4. Instalar el módulo

## Uso

1. Ir a **Contabilidad > Reportes > Análisis de Facturas**
2. El campo "Cliente (Código - Nombre)" aparecerá junto al campo "Partner"
3. Puedes usar este campo para:
   - Ordenar por código de cliente
   - Filtrar/buscar por código o nombre
   - Agrupar en reportes pivot y gráficos

## Dependencias

- `account`: Módulo de contabilidad de Odoo

## Versión

- Odoo 18.0
- Versión del módulo: 1.0.0

## Autor

SNG

## Licencia

LGPL-3
