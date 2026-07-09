# -*- coding: utf-8 -*-
from odoo import fields, models


class StockLocationReportWarehouseLine(models.Model):
    _name = "stock.location.report.warehouse.line"
    _description = "Desglose por Bodega del Reporte de Movimientos"
    _order = "product_name, warehouse_name"

    report_id = fields.Many2one(
        comodel_name="stock.location.report",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        required=True,
        readonly=True,
    )
    default_code = fields.Char(string="Código", readonly=True)
    product_name = fields.Char(string="Nombre del Producto", readonly=True)
    uom_id = fields.Many2one(comodel_name="uom.uom", string="Unidad de Medida", readonly=True)
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Almacén",
        required=True,
        readonly=True,
    )
    warehouse_name = fields.Char(string="Almacén", readonly=True)
    saldo_inicial_qty = fields.Float(
        string="Saldo Inicial",
        digits="Product Unit of Measure",
        readonly=True,
    )
    entradas_qty = fields.Float(
        string="Entradas",
        digits="Product Unit of Measure",
        readonly=True,
    )
    salidas_qty = fields.Float(
        string="Salidas",
        digits="Product Unit of Measure",
        readonly=True,
    )
    fisico_qty = fields.Float(
        string="Cantidad Física",
        digits="Product Unit of Measure",
        readonly=True,
    )
    reservado_qty = fields.Float(
        string="Reservado",
        digits="Product Unit of Measure",
        readonly=True,
    )
    disponible_qty = fields.Float(
        string="Disponible",
        digits="Product Unit of Measure",
        readonly=True,
    )
