# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLocationReportLine(models.Model):
    _name = "stock.location.report.line"
    _description = "Línea de Reporte de Movimientos por Ubicación"
    _order = "product_name"

    report_id = fields.Many2one(
        comodel_name="stock.location.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto",
        required=True,
        readonly=True,
    )
    default_code = fields.Char(
        string="Código",
        readonly=True,
    )
    product_name = fields.Char(
        string="Nombre del Producto",
        readonly=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unidad de Medida",
        readonly=True,
    )
    
    # Cantidades
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
    movimiento_net = fields.Float(
        string="Movimiento Neto",
        compute="_compute_movimiento_net",
        digits="Product Unit of Measure",
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

    @api.depends("entradas_qty", "salidas_qty")
    def _compute_movimiento_net(self):
        for line in self:
            line.movimiento_net = line.entradas_qty - line.salidas_qty
