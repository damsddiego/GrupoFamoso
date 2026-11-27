# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools import SQL


class SngComercialInventarioReport(models.Model):
    _name = 'sng.comercial.inventario.report'
    _description = 'Inventario comercial'
    _auto = False
    _rec_name = 'product_id'
    _order = 'company_id, default_code, id'

    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Plantilla de producto', readonly=True)
    default_code = fields.Char(string='Código', readonly=True)
    categ_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    pilar_id = fields.Many2one('product.attribute.value', string='Pilar', readonly=True)
    base_id = fields.Many2one('product.attribute.value', string='Base', readonly=True)
    volumen_id = fields.Many2one('product.attribute.value', string='Volumen', readonly=True)
    litros_unidad = fields.Float(string='Litros por unidad', readonly=True, aggregator=None)
    stock = fields.Float(string='Stock', readonly=True)
    transito = fields.Float(string='Tránsito', readonly=True)
    bodega_grupo = fields.Float(string='Bodega grupo', readonly=True)
    total = fields.Float(string='Total', readonly=True)
    total_litros = fields.Float(string='Total litros', readonly=True)

    @property
    def _table_query(self) -> SQL:
        """Una fila por producto con pilar y compañía. Un producto compartido
        (sin compañía) solo sale en las compañías donde tiene stock o tránsito."""
        return SQL(
            """
            SELECT pp.id * 1000 + c.id                                AS id,
                   c.id                                               AS company_id,
                   pp.id                                              AS product_id,
                   pp.product_tmpl_id                                 AS product_tmpl_id,
                   pp.default_code                                    AS default_code,
                   pt.categ_id                                        AS categ_id,
                   pt.sng_pilar_id                                    AS pilar_id,
                   pt.sng_base_id                                     AS base_id,
                   pt.sng_volumen_id                                  AS volumen_id,
                   COALESCE(pt.sng_litros_unidad, 0)                  AS litros_unidad,
                   COALESCE(s.qty, 0)                                 AS stock,
                   COALESCE(t.qty, 0)                                 AS transito,
                   COALESCE(b.qty, 0)                                 AS bodega_grupo,
                   COALESCE(s.qty, 0) + COALESCE(t.qty, 0) + COALESCE(b.qty, 0) AS total,
                   (COALESCE(s.qty, 0) + COALESCE(t.qty, 0) + COALESCE(b.qty, 0))
                       * COALESCE(pt.sng_litros_unidad, 0)            AS total_litros
              FROM product_product pp
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              JOIN uom_uom pu          ON pu.id = pt.uom_id
              JOIN res_company c       ON c.id = pt.company_id OR pt.company_id IS NULL
              /* Stock propio en ubicaciones internas */
              LEFT JOIN LATERAL (
                    SELECT SUM(q.quantity) AS qty
                      FROM stock_quant q
                      JOIN stock_location sl ON sl.id = q.location_id
                     WHERE q.product_id = pp.id
                       AND q.company_id = c.id
                       AND sl.usage = 'internal'
                   ) s ON TRUE
              /* Tránsito: pendiente de recibir en órdenes de compra confirmadas */
              LEFT JOIN LATERAL (
                    SELECT SUM((pol.product_qty - pol.qty_received) / lu.factor * pu.factor) AS qty
                      FROM purchase_order_line pol
                      JOIN purchase_order po ON po.id = pol.order_id
                      JOIN uom_uom lu        ON lu.id = pol.product_uom
                     WHERE pol.product_id = pp.id
                       AND po.company_id = c.id
                       AND po.state = 'purchase'
                       AND pol.product_qty > pol.qty_received
                   ) t ON TRUE
              /* Bodega del grupo: misma referencia interna en la compañía bodega */
              LEFT JOIN LATERAL (
                    SELECT SUM(q.quantity) AS qty
                      FROM stock_quant q
                      JOIN stock_location sl  ON sl.id = q.location_id
                      JOIN product_product p2 ON p2.id = q.product_id
                     WHERE c.sng_comercial_bodega_company_id IS NOT NULL
                       AND q.company_id = c.sng_comercial_bodega_company_id
                       AND sl.usage = 'internal'
                       AND p2.default_code = pp.default_code
                   ) b ON TRUE
             WHERE pp.active
               AND pt.active
               AND pt.sng_pilar_id IS NOT NULL
               AND (pt.company_id IS NOT NULL
                    OR COALESCE(s.qty, 0) <> 0
                    OR COALESCE(t.qty, 0) <> 0)
            """
        )
