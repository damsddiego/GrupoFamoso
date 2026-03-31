# -*- coding: utf-8 -*-
"""
Asistente (wizard) para generar el reporte PDF del catálogo de productos.

DECISIÓN TÉCNICA: product.template vs product.product
======================================================
Se usa **product.template** como modelo base por estas razones:

1. `default_code` (referencia interna) vive en product.template, no en product.product.
   Usar product.product duplicaría filas para productos con múltiples variantes
   (ej. una camiseta talla S/M/L aparecería 3 veces).

2. `list_price` (precio de venta) está en product.template.

3. `qty_available` en product.template agrega automáticamente todas las variantes
   usando stock.quant para todas las ubicaciones internas.

4. Un catálogo de inventario debe mostrar UN registro por producto,
   no uno por variante. Si el usuario necesita ver variantes, puede extender el módulo.

Resultado: una fila por producto, con cantidad y precio a nivel de template.
"""

from odoo import models, fields
from odoo.exceptions import UserError


class InventoryCatalogWizard(models.TransientModel):
    """
    Wizard para configurar y lanzar el reporte PDF del catálogo de productos.
    Al presionar 'Generar PDF', se llama action_generate_report() que
    retorna la acción del reporte con este registro como doc.
    """
    _name = 'inventory.catalog.wizard'
    _description = 'Asistente - Catálogo de Productos por Categoría'

    # ------------------------------------------------------------------
    # Campos del formulario wizard
    # ------------------------------------------------------------------

    category_ids = fields.Many2many(
        comodel_name='product.category',
        string='Categorías de Producto',
        help=(
            'Selecciona las categorías a incluir en el reporte. '
            'Si se deja vacío, se incluirán TODAS las categorías.'
        ),
    )
    include_subcategories = fields.Boolean(
        string='Incluir subcategorías',
        default=True,
        help=(
            'Si está activo, incluye recursivamente todas las subcategorías '
            'de las categorías seleccionadas.'
        ),
    )
    only_active = fields.Boolean(
        string='Solo productos activos',
        default=True,
        help='Si está activo, excluye los productos archivados del reporte.',
    )
    include_no_stock = fields.Boolean(
        string='Incluir productos sin existencia',
        default=True,
        help=(
            'Si está activo, incluye productos con cantidad disponible igual a cero. '
            'Si está inactivo, solo se muestran productos con stock positivo.'
        ),
    )
    group_by_category = fields.Boolean(
        string='Agrupar por categoría',
        default=True,
        help=(
            'Si está activo, el reporte agrupa los productos por categoría. '
            'Si está inactivo, muestra todos los productos en una lista plana '
            'ordenada alfabéticamente por nombre.'
        ),
    )

    # ------------------------------------------------------------------
    # Métodos privados: lógica de filtros y consultas
    # ------------------------------------------------------------------

    def _get_expanded_category_ids(self):
        """
        Retorna lista de IDs de categorías a filtrar.

        Si include_subcategories está activo, usa el operador 'child_of'
        de Odoo, que recorre la jerarquía de forma eficiente mediante
        la columna 'parent_path' indexada de product.category.

        Retorna lista vacía si no hay categorías seleccionadas
        (lo que significa 'todas las categorías').
        """
        if not self.category_ids:
            return []

        if self.include_subcategories:
            # child_of: busca el registro y todos sus descendientes
            # usando parent_path (equivalente a un LIKE en SQL, muy eficiente)
            all_categories = self.env['product.category'].search([
                ('id', 'child_of', self.category_ids.ids)
            ])
            return all_categories.ids

        return self.category_ids.ids

    def _build_product_domain(self):
        """
        Construye el dominio ORM para buscar en product.template
        según los filtros del wizard.
        """
        domain = []

        # Solo activos: active=True es el default en Odoo, pero cuando
        # only_active=False necesitamos desactivar active_test en context
        # (se maneja en _get_products, no aquí).
        if self.only_active:
            domain.append(('active', '=', True))

        # Filtro por categorías expandidas
        cat_ids = self._get_expanded_category_ids()
        if cat_ids:
            domain.append(('categ_id', 'in', cat_ids))

        return domain

    def _get_template_ids_with_stock(self):
        """
        Retorna un conjunto (set) de product.template IDs que tienen
        cantidad disponible mayor a cero en ubicaciones internas.

        Estrategia eficiente en 2 queries SQL vía ORM:
        1. read_group en stock.quant agrupado por product_id
           → obtiene suma de (quantity - reserved_quantity) por variante
        2. search_read en product.product para mapear pp_id → tmpl_id

        Esto evita iterar sobre cada producto y calcular qty_available
        uno por uno (que generaría N queries).
        """
        # Query 1: suma de qty disponible por product.product en ubicaciones internas
        quant_data = self.env['stock.quant'].read_group(
            domain=[('location_id.usage', '=', 'internal')],
            fields=['product_id', 'quantity:sum', 'reserved_quantity:sum'],
            groupby=['product_id'],
        )

        # Filtramos variantes con cantidad disponible > 0
        pp_ids_with_stock = [
            row['product_id'][0]
            for row in quant_data
            if row['product_id']
            and (row['quantity'] - row['reserved_quantity']) > 0
        ]

        if not pp_ids_with_stock:
            return set()

        # Query 2: convertir product.product IDs → product.template IDs en un solo read
        pp_data = self.env['product.product'].search_read(
            domain=[('id', 'in', pp_ids_with_stock)],
            fields=['product_tmpl_id'],
        )

        return {row['product_tmpl_id'][0] for row in pp_data if row['product_tmpl_id']}

    # ------------------------------------------------------------------
    # Método principal: datos para la plantilla QWeb
    # ------------------------------------------------------------------

    def get_grouped_products(self):
        """
        Método principal llamado desde la plantilla QWeb del reporte.

        Retorna una lista de grupos ordenados por nombre de categoría:
        [
            {
                'category_name': str,           # nombre de la categoría
                'category':      product.category record,
                'products':      list of dicts,
                'subtotal':      float,          # suma de (qty * precio) del grupo
            },
            ...
        ]

        Cada dict de producto tiene:
        {
            'default_code':  str,    # referencia interna
            'name':          str,    # nombre del producto
            'qty_available': float,  # cantidad disponible total
            'list_price':    float,  # precio de venta
        }
        """
        self.ensure_one()

        # Contexto: desactivar active_test permite ver archivados si only_active=False
        ctx = dict(self.env.context, active_test=self.only_active)
        domain = self._build_product_domain()

        # Orden: si se agrupa por categoría → categ_id, name; si no → solo name
        order = 'categ_id, name' if self.group_by_category else 'name'
        products = self.env['product.template'].with_context(ctx).search(
            domain, order=order
        )

        # Filtro de stock: si se excluyen sin existencia, calculamos
        # los template IDs con stock y aplicamos el filtro en Python
        # (qty_available no es campo almacenado; no se puede filtrar en SQL)
        if not self.include_no_stock:
            tmpl_ids_with_stock = self._get_template_ids_with_stock()
            products = products.filtered(lambda p: p.id in tmpl_ids_with_stock)

        if not products:
            return []

        # Pre-carga qty_available para todos los productos en una sola llamada SQL
        products.mapped('qty_available')

        # ── MODO PLANO: lista única sin agrupación, ya ordenada por nombre ──
        if not self.group_by_category:
            flat_products = []
            total_qty = 0.0
            subtotal = 0.0
            for product in products:
                qty = product.qty_available
                price = product.list_price
                total_qty += qty
                subtotal += qty * price
                flat_products.append({
                    'default_code': product.default_code or '---',
                    'name': product.name or '',
                    'qty_available': qty,
                    'list_price': price,
                })
            return [{
                'category_name': False,   # False = no mostrar cabecera en template
                'category': False,
                'products': flat_products,
                'total_qty': total_qty,
                'subtotal': subtotal,
            }]

        # ── MODO AGRUPADO: agrupar por categoría ──
        grouped = {}  # key: categ_id (int), value: dict del grupo

        for product in products:
            categ = product.categ_id
            categ_key = categ.id if categ else 0

            if categ_key not in grouped:
                grouped[categ_key] = {
                    'category': categ,
                    'category_name': categ.complete_name if categ else 'Sin categoría',
                    'products': [],
                    'total_qty': 0.0,
                    'subtotal': 0.0,
                }

            qty = product.qty_available
            price = product.list_price

            grouped[categ_key]['total_qty'] += qty
            grouped[categ_key]['products'].append({
                'default_code': product.default_code or '---',
                'name': product.name or '',
                'qty_available': qty,
                'list_price': price,
            })

            grouped[categ_key]['subtotal'] += qty * price

        # Ordenar grupos por nombre de categoría (case-insensitive)
        result = sorted(
            grouped.values(),
            key=lambda g: (g['category_name'] or '').lower()
        )

        return result

    def get_filter_description(self):
        """
        Genera texto descriptivo de los filtros aplicados.
        Se muestra en el encabezado del PDF.
        """
        self.ensure_one()
        parts = []

        if self.category_ids:
            names = ', '.join(self.category_ids.mapped('name'))
            sub = ' (+ subcategorías)' if self.include_subcategories else ''
            parts.append(f'Categorías: {names}{sub}')
        else:
            parts.append('Categorías: Todas')

        parts.append('Activos: Sí' if self.only_active else 'Activos: Sí/No')
        parts.append(
            'Sin stock: Incluido' if self.include_no_stock else 'Sin stock: Excluido'
        )
        parts.append(
            'Orden: por categoría' if self.group_by_category else 'Orden: alfabético'
        )

        return '  |  '.join(parts)

    def format_price(self, price):
        """
        Formatea un precio con el símbolo de la moneda de la empresa.
        Se llama desde la plantilla QWeb.
        """
        currency = self.env.company.currency_id
        formatted = f'{price:,.2f}'
        if currency.position == 'before':
            return f'{currency.symbol} {formatted}'
        return f'{formatted} {currency.symbol}'

    def format_qty(self, qty):
        """Formatea cantidad con 2 decimales. Se llama desde la plantilla QWeb."""
        return f'{qty:,.2f}'

    def get_report_datetime(self):
        """Retorna fecha y hora actual formateada. Se llama desde la plantilla QWeb."""
        from datetime import datetime
        return datetime.now().strftime('%d/%m/%Y %H:%M')

    # ------------------------------------------------------------------
    # Acciones de los botones del wizard
    # ------------------------------------------------------------------

    def action_generate_report(self):
        """
        Botón 'Generar PDF': construye y retorna la acción del reporte.
        Odoo pasará este registro (self) como 'docs' a la plantilla QWeb.
        """
        self.ensure_one()
        return self.env.ref(
            'sng_inventory_catalog_pdf.action_report_inventory_catalog'
        ).report_action(self)

    def action_export_excel(self):
        """
        Botón 'Exportar Excel': genera el archivo .xlsx y lo descarga.

        El archivo se protege contra edición (worksheet.protect) para que
        precio y cantidad no puedan ser modificados por el usuario.
        Sí se permite seleccionar celdas, copiar y ordenar.
        """
        import io
        import base64
        import xlsxwriter
        from datetime import datetime

        self.ensure_one()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Catálogo')

        # ── Formatos ──────────────────────────────────────────────────
        # Nota: locked=True es el default en Excel/xlsxwriter.
        # Solo tiene efecto cuando se activa worksheet.protect().

        def _fmt(**kw):
            base = {'locked': True, 'valign': 'vcenter', 'font_size': 9}
            base.update(kw)
            return workbook.add_format(base)

        fmt_company   = _fmt(bold=True, font_size=13, align='center')
        fmt_title     = _fmt(bold=True, font_size=11, align='center',
                             font_color='#1a3a5c')
        fmt_meta_lbl  = _fmt(bold=True, font_size=9)
        fmt_meta_val  = _fmt(font_size=9)
        fmt_cat       = _fmt(bold=True, font_size=10, bg_color='#1a3a5c',
                             font_color='#ffffff', border=1)
        fmt_col_hdr   = _fmt(bold=True, bg_color='#dde7f0', font_color='#1a3a5c',
                             border=1, align='center')
        fmt_even_txt  = _fmt(bg_color='#f7fafd', border=1)
        fmt_odd_txt   = _fmt(bg_color='#ffffff', border=1)
        fmt_even_num  = _fmt(bg_color='#f7fafd', border=1,
                             num_format='#,##0.00', align='right')
        fmt_odd_num   = _fmt(bg_color='#ffffff', border=1,
                             num_format='#,##0.00', align='right')

        # ── Anchos de columna ──────────────────────────────────────────
        ws.set_column('A:A', 18)   # Código
        ws.set_column('B:B', 52)   # Nombre
        ws.set_column('C:C', 20)   # Cant. Disponible
        ws.set_column('D:D', 18)   # Precio

        # ── Bloque de encabezado ───────────────────────────────────────
        row = 0
        ws.set_row(row, 20)
        ws.merge_range(row, 0, row, 3, self.env.company.name, fmt_company)
        row += 1

        ws.set_row(row, 18)
        ws.merge_range(row, 0, row, 3,
                       'Catálogo de Productos por Categoría', fmt_title)
        row += 1

        ws.write(row, 0, 'Fecha:',         fmt_meta_lbl)
        ws.write(row, 1, datetime.now().strftime('%d/%m/%Y %H:%M'), fmt_meta_val)
        ws.write(row, 2, 'Generado por:',  fmt_meta_lbl)
        ws.write(row, 3, self.env.user.name, fmt_meta_val)
        row += 1

        ws.write(row, 0, 'Filtros:', fmt_meta_lbl)
        ws.merge_range(row, 1, row, 3,
                       self.get_filter_description(), fmt_meta_val)
        row += 2   # fila vacía de separación

        # ── Datos ──────────────────────────────────────────────────────
        grouped_data = self.get_grouped_products()

        if not grouped_data:
            ws.merge_range(row, 0, row, 3,
                           'No se encontraron productos con los filtros seleccionados.',
                           fmt_meta_val)
            workbook.close()
            output.seek(0)
            return self._return_excel_download(
                base64.b64encode(output.read()), 'catalogo_productos.xlsx'
            )

        # Fila a partir de la cual están los datos (para autofilter en modo plano)
        data_start_row = row

        for group in grouped_data:
            # Cabecera de categoría (solo en modo agrupado)
            if self.group_by_category and group['category_name']:
                ws.set_row(row, 16)
                label = f"{group['category_name']}  ({len(group['products'])} productos)"
                ws.merge_range(row, 0, row, 3, label, fmt_cat)
                row += 1

            # Encabezados de columna
            ws.write(row, 0, 'Código',           fmt_col_hdr)
            ws.write(row, 1, 'Nombre / Descripción', fmt_col_hdr)
            ws.write(row, 2, 'Cant. Disponible', fmt_col_hdr)
            ws.write(row, 3, 'Precio de Venta',  fmt_col_hdr)
            row += 1

            # Filas de productos
            for idx, product in enumerate(group['products']):
                fmt_t = fmt_even_txt if idx % 2 == 0 else fmt_odd_txt
                fmt_n = fmt_even_num if idx % 2 == 0 else fmt_odd_num
                ws.write(row, 0, product['default_code'],  fmt_t)
                ws.write(row, 1, product['name'],          fmt_t)
                ws.write(row, 2, product['qty_available'], fmt_n)
                ws.write(row, 3, product['list_price'],    fmt_n)
                row += 1

            row += 1   # fila vacía entre grupos

        # Autofilter en modo plano (una sola tabla continua)
        if not self.group_by_category:
            ws.autofilter(data_start_row, 0, row - 1, 3)

        # Congelar las filas de encabezado del reporte
        ws.freeze_panes(data_start_row, 0)

        # ── Protección contra edición ──────────────────────────────────
        # Todas las celdas tienen locked=True (default). Al activar protect(),
        # ninguna celda podrá editarse. El usuario puede seleccionar y copiar.
        ws.protect('', {
            'select_locked_cells':   True,   # puede seleccionar celdas bloqueadas
            'select_unlocked_cells': True,   # puede seleccionar celdas libres
            'sort':                  True,   # puede ordenar
            'autofilter':            True,   # puede usar filtros automáticos
            'format_cells':          False,
            'format_columns':        False,
            'format_rows':           False,
            'insert_rows':           False,
            'insert_columns':        False,
            'delete_rows':           False,
            'delete_columns':        False,
        })

        workbook.close()
        output.seek(0)
        return self._return_excel_download(
            base64.b64encode(output.read()), 'catalogo_productos.xlsx'
        )

    def _return_excel_download(self, b64_data, filename):
        """Crea un ir.attachment temporal y retorna la acción de descarga."""
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': b64_data,
            'mimetype': (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_cancel(self):
        """Botón 'Cancelar': cierra el wizard sin generar reporte."""
        return {'type': 'ir.actions.act_window_close'}
