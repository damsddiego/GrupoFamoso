# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class SngProductNoImage(models.Model):
    _name = 'sng.product.no.image'
    _description = 'Artículos sin Imagen'
    _auto = False
    _order = 'company_id, default_code, product_name'
    _rec_name = 'product_name'

    product_tmpl_id = fields.Many2one(
        'product.template', string='Producto', readonly=True)
    default_code = fields.Char(string='Código', readonly=True)
    product_name = fields.Char(string='Descripción', readonly=True)
    barcode = fields.Char(string='Código de barras', readonly=True)
    categ_id = fields.Many2one(
        'product.category', string='Categoría', readonly=True)
    type = fields.Selection(
        [('consu', 'Bien'), ('service', 'Servicio'), ('combo', 'Combo')],
        string='Tipo', readonly=True)
    is_storable = fields.Boolean(string='Se almacena', readonly=True)
    list_price = fields.Float(string='Precio de venta', readonly=True)
    sale_ok = fields.Boolean(string='Se puede vender', readonly=True)
    purchase_ok = fields.Boolean(string='Se puede comprar', readonly=True)
    extra_image_count = fields.Integer(
        string='Imágenes extra', readonly=True,
        help='Cantidad de imágenes adicionales cargadas en la pestaña de '
             'imágenes del producto. Si es mayor a 0, el producto tiene fotos '
             'pero ninguna como imagen principal.')
    create_date = fields.Datetime(string='Fecha de creación', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    pt.id                                AS id,
                    pt.id                                AS product_tmpl_id,
                    pt.default_code                      AS default_code,
                    COALESCE(pt.name ->> 'es_CR',
                             pt.name ->> 'es_ES',
                             pt.name ->> 'en_US')        AS product_name,
                    pp.barcode                           AS barcode,
                    pt.categ_id                          AS categ_id,
                    pt.type                              AS type,
                    pt.is_storable                       AS is_storable,
                    pt.list_price                        AS list_price,
                    pt.sale_ok                           AS sale_ok,
                    pt.purchase_ok                       AS purchase_ok,
                    COALESCE(pi.cnt, 0)                  AS extra_image_count,
                    pt.create_date                       AS create_date,
                    pt.company_id                        AS company_id
                FROM product_template pt
                LEFT JOIN LATERAL (
                    SELECT p.barcode
                    FROM product_product p
                    WHERE p.product_tmpl_id = pt.id
                      AND p.active
                      AND p.barcode IS NOT NULL
                    ORDER BY p.id
                    LIMIT 1
                ) pp ON TRUE
                LEFT JOIN (
                    SELECT product_tmpl_id, COUNT(*) AS cnt
                    FROM product_image
                    GROUP BY product_tmpl_id
                ) pi ON pi.product_tmpl_id = pt.id
                WHERE pt.active
                  AND NOT EXISTS (
                        SELECT 1
                        FROM ir_attachment a
                        WHERE a.res_model = 'product.template'
                          AND a.res_field = 'image_1920'
                          AND a.res_id = pt.id
                          AND COALESCE(a.file_size, 0) > 0
                  )
            )
        """ % (self._table,))

    def action_open_product(self):
        """Abrir la ficha del producto para cargarle la imagen."""
        self.ensure_one()
        return {
            'name': self.product_name or 'Producto',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.product_tmpl_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
