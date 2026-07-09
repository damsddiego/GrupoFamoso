# -*- coding: utf-8 -*-
from odoo import fields, models


class StockKardexReportLine(models.TransientModel):
    _name = "stock.kardex.report.line"
    _description = "Línea de Kardex"
    _order = "date, id"

    wizard_id = fields.Many2one("stock.kardex.wizard", string="Wizard", ondelete="cascade")
    date = fields.Datetime(string="Fecha")
    reference = fields.Char(string="Referencia")
    origin = fields.Char(string="Origen")
    picking_type_id = fields.Many2one("stock.picking.type", string="Tipo de operación")
    location_id = fields.Many2one("stock.location", string="Ubicación origen")
    location_dest_id = fields.Many2one("stock.location", string="Ubicación destino")
    qty_in = fields.Float(string="Entrada", digits="Product Unit of Measure")
    qty_out = fields.Float(string="Salida", digits="Product Unit of Measure")
    balance = fields.Float(string="Saldo", digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", string="UdM")
    reserved_qty = fields.Float(string="Reservado", digits="Product Unit of Measure")
    move_id = fields.Many2one("stock.move", string="Movimiento")
