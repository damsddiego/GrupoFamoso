# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    """
    Extensión del modelo sale.order para agregar campo que indica
    si la orden tiene al menos una factura asociada.

    Este campo permite filtrar de forma eficiente las órdenes que
    ya tienen facturas, excluyéndolas de la vista "Pendiente por facturar".
    """
    _inherit = 'sale.order'

    # ========================================================================
    # FIELDS
    # ========================================================================

    has_invoice = fields.Boolean(
        string='Has Invoice',
        compute='_compute_has_invoice',
        store=True,
        help="Campo técnico que indica si esta orden de venta tiene al menos "
             "una factura asociada (sin importar el estado de la factura). "
             "Se utiliza para filtrar órdenes en la vista 'Pendiente por facturar'."
    )

    # ========================================================================
    # COMPUTE METHODS
    # ========================================================================

    @api.depends('order_line.invoice_lines')
    def _compute_has_invoice(self):
        """
        Calcula si la orden de venta tiene al menos una factura asociada.

        **Lógica:**
        - Se basa en el campo nativo 'invoice_ids' (Many2many computado)
        - invoice_ids se calcula a partir de order_line.invoice_lines
        - Si existe al menos una factura vinculada, has_invoice = True
        - Si no hay facturas vinculadas, has_invoice = False

        **Dependencias:**
        - Depende de 'order_line.invoice_lines' (campo que vincula líneas de orden
          con líneas de factura)
        - Cuando se crea/modifica/elimina una factura desde una orden, se actualiza
          automáticamente order_line.invoice_lines, lo que dispara este compute

        **Ventajas de almacenar (store=True):**
        - Mejora el rendimiento al filtrar en vistas (no requiere joins complejos)
        - Permite búsquedas rápidas en dominios
        - Se actualiza automáticamente cuando cambia invoice_lines

        **Casos cubiertos:**
        - Facturas en borrador, validadas, canceladas (todas cuentan)
        - Facturas de anticipo (down payment)
        - Facturas parciales o totales
        - Cualquier factura vinculada a través de account.move.line
        """
        for order in self:
            # Utilizamos invoice_ids que es un campo Many2many computado nativo
            # que obtiene todas las facturas relacionadas con esta orden
            order.has_invoice = bool(order.invoice_ids)

    # ========================================================================
    # ALTERNATIVE IMPLEMENTATION (Comentado - más eficiente para grandes BD)
    # ========================================================================

    # Si en el futuro se requiere optimizar aún más para bases de datos muy grandes
    # con millones de registros, se puede usar esta implementación alternativa que
    # evita cargar los registros de invoice_ids en memoria:

    # @api.depends('order_line.invoice_lines')
    # def _compute_has_invoice(self):
    #     """
    #     Implementación optimizada usando SQL para grandes volúmenes de datos.
    #     """
    #     if not self:
    #         return
    #
    #     # Query SQL directa para verificar si existe al menos una factura
    #     self._cr.execute("""
    #         SELECT so.id
    #         FROM sale_order so
    #         INNER JOIN sale_order_line sol ON sol.order_id = so.id
    #         INNER JOIN sale_order_line_invoice_rel solir ON solir.order_line_id = sol.id
    #         WHERE so.id IN %s
    #         GROUP BY so.id
    #     """, (tuple(self.ids),))
    #
    #     orders_with_invoices = set(row[0] for row in self._cr.fetchall())
    #
    #     for order in self:
    #         order.has_invoice = order.id in orders_with_invoices
