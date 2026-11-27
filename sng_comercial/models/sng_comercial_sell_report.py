# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools import SQL

# Las recepciones se guardan en UTC; el mes comercial es el de Costa Rica.
ZONA_HORARIA = 'America/Costa_Rica'


class SngComercialSellReport(models.Model):
    _name = 'sng.comercial.sell.report'
    _description = 'Sell in / Sell out'
    _auto = False
    _rec_name = 'product_id'
    _order = 'date desc, id desc'

    date = fields.Date(string='Fecha', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Plantilla de producto', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    pilar_id = fields.Many2one('product.attribute.value', string='Pilar', readonly=True)
    base_id = fields.Many2one('product.attribute.value', string='Base', readonly=True)
    volumen_id = fields.Many2one('product.attribute.value', string='Volumen', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor / Cliente', readonly=True)
    documento = fields.Char(string='Documento', readonly=True)
    tipo = fields.Selection(
        [('sell_in', 'Sell in'), ('sell_out', 'Sell out')], string='Tipo', readonly=True)
    cantidad = fields.Float(string='Unidades', readonly=True)
    litros = fields.Float(string='Litros', readonly=True)
    qty_in = fields.Float(string='Sell in (unidades)', readonly=True)
    litros_in = fields.Float(string='Sell in (litros)', readonly=True)
    qty_out = fields.Float(string='Sell out (unidades)', readonly=True)
    litros_out = fields.Float(string='Sell out (litros)', readonly=True)

    @property
    def _table_query(self) -> SQL:
        return SQL(
            """
            SELECT mov.id, mov.date, mov.company_id, mov.product_id, mov.product_tmpl_id,
                   mov.categ_id, mov.pilar_id, mov.base_id, mov.volumen_id, mov.partner_id,
                   mov.documento, mov.tipo,
                   mov.cantidad,
                   mov.cantidad * mov.litros_unidad                              AS litros,
                   CASE WHEN mov.tipo = 'sell_in' THEN mov.cantidad ELSE 0 END   AS qty_in,
                   CASE WHEN mov.tipo = 'sell_in'
                        THEN mov.cantidad * mov.litros_unidad ELSE 0 END         AS litros_in,
                   CASE WHEN mov.tipo = 'sell_out' THEN mov.cantidad ELSE 0 END  AS qty_out,
                   CASE WHEN mov.tipo = 'sell_out'
                        THEN mov.cantidad * mov.litros_unidad ELSE 0 END         AS litros_out
              FROM (%s UNION ALL %s) mov
            """,
            self._sell_in_query(), self._sell_out_query(),
        )

    def _sell_in_query(self) -> SQL:
        """Compras recibidas: movimientos hechos ligados a una línea de OC.
        Entrar a una ubicación interna suma; salir de ella (devolución al
        proveedor) resta. La cantidad va en la unidad del producto."""
        return SQL(
            """
            SELECT m.id * 2                                                  AS id,
                   (m.date AT TIME ZONE 'UTC' AT TIME ZONE %(tz)s)::date     AS date,
                   m.company_id                                              AS company_id,
                   m.product_id                                              AS product_id,
                   pp.product_tmpl_id                                        AS product_tmpl_id,
                   pt.categ_id                                               AS categ_id,
                   pt.sng_pilar_id                                           AS pilar_id,
                   pt.sng_base_id                                            AS base_id,
                   pt.sng_volumen_id                                         AS volumen_id,
                   po.partner_id                                             AS partner_id,
                   po.name                                                   AS documento,
                   'sell_in'                                                 AS tipo,
                   CASE WHEN ld.usage = 'internal' THEN 1 ELSE -1 END
                       * m.quantity / mu.factor * pu.factor                  AS cantidad,
                   COALESCE(pt.sng_litros_unidad, 0)                         AS litros_unidad
              FROM stock_move m
              JOIN stock_location ls       ON ls.id = m.location_id
              JOIN stock_location ld       ON ld.id = m.location_dest_id
              JOIN purchase_order_line pol ON pol.id = m.purchase_line_id
              JOIN purchase_order po       ON po.id = pol.order_id
              JOIN product_product pp      ON pp.id = m.product_id
              JOIN product_template pt     ON pt.id = pp.product_tmpl_id
              JOIN uom_uom mu              ON mu.id = m.product_uom
              JOIN uom_uom pu              ON pu.id = pt.uom_id
             WHERE m.state = 'done'
               AND pt.sng_pilar_id IS NOT NULL
               AND (ls.usage = 'internal') <> (ld.usage = 'internal')
            """,
            tz=ZONA_HORARIA,
        )

    def _sell_out_query(self) -> SQL:
        """Ventas facturadas: líneas de factura publicada ligadas a una línea
        de orden de venta. Las notas de crédito restan."""
        return SQL(
            """
            SELECT l.id * 2 + 1                                              AS id,
                   am.invoice_date                                           AS date,
                   am.company_id                                             AS company_id,
                   l.product_id                                              AS product_id,
                   pp.product_tmpl_id                                        AS product_tmpl_id,
                   pt.categ_id                                               AS categ_id,
                   pt.sng_pilar_id                                           AS pilar_id,
                   pt.sng_base_id                                            AS base_id,
                   pt.sng_volumen_id                                         AS volumen_id,
                   am.commercial_partner_id                                  AS partner_id,
                   am.name                                                   AS documento,
                   'sell_out'                                                AS tipo,
                   CASE WHEN am.move_type = 'out_refund' THEN -1 ELSE 1 END
                       * l.quantity / COALESCE(lu.factor, pu.factor) * pu.factor AS cantidad,
                   COALESCE(pt.sng_litros_unidad, 0)                         AS litros_unidad
              FROM account_move_line l
              JOIN account_move am         ON am.id = l.move_id
              JOIN product_product pp      ON pp.id = l.product_id
              JOIN product_template pt     ON pt.id = pp.product_tmpl_id
              JOIN uom_uom pu              ON pu.id = pt.uom_id
              LEFT JOIN uom_uom lu         ON lu.id = l.product_uom_id
             WHERE am.state = 'posted'
               AND am.move_type IN ('out_invoice', 'out_refund')
               AND l.display_type = 'product'
               AND pt.sng_pilar_id IS NOT NULL
               AND EXISTS (SELECT 1
                             FROM sale_order_line_invoice_rel rel
                            WHERE rel.invoice_line_id = l.id)
            """
        )
