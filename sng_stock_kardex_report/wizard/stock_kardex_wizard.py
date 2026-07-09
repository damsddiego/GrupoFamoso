# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockKardexWizard(models.TransientModel):
    _name = "stock.kardex.wizard"
    _description = "Wizard Kardex de Inventario"

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain=[("is_storable", "=", True)],
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación",
        domain=[("usage", "=", "internal")],
        help="Si se selecciona una ubicación, el kardex mostrará únicamente los movimientos que afecten dicha ubicación y el saldo se calculará para esa ubicación. Si se deja vacío, se mostrará el kardex global del producto.",
    )
    date_from = fields.Datetime(
        string="Desde",
        required=True,
        default=lambda self: fields.Datetime.now().replace(day=1, hour=0, minute=0, second=0),
    )
    date_to = fields.Datetime(
        string="Hasta",
        required=True,
        default=fields.Datetime.now,
    )
    line_ids = fields.One2many(
        "stock.kardex.report.line",
        "wizard_id",
        string="Líneas",
    )

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            self.date_to = self.date_from

    def _get_balance_start(self):
        """Calcula el saldo inicial antes de la fecha desde."""
        self.ensure_one()
        product = self.product_id.with_context(to_date=self.date_from)
        if self.location_id:
            product = product.with_context(location=self.location_id.id)
        return product.qty_available

    def _is_in_move(self, move_line):
        """Determina si el movimiento es una entrada."""
        if self.location_id:
            return move_line.location_dest_id == self.location_id
        return (
            move_line.location_dest_id.usage in ("internal", "transit")
            and move_line.location_id.usage not in ("internal", "transit")
        )

    def _is_out_move(self, move_line):
        """Determina si el movimiento es una salida."""
        if self.location_id:
            return move_line.location_id == self.location_id
        return (
            move_line.location_id.usage in ("internal", "transit")
            and move_line.location_dest_id.usage not in ("internal", "transit")
        )

    def action_generate(self):
        self.ensure_one()
        self.line_ids.unlink()

        balance = self._get_balance_start()

        quant_domain = [("product_id", "=", self.product_id.id)]
        if self.location_id:
            quant_domain.append(("location_id", "child_of", self.location_id.id))
        else:
            quant_domain.append(("location_id.usage", "=", "internal"))
        quants = self.env["stock.quant"].sudo().search(quant_domain)
        current_reserved = sum(quants.mapped("reserved_quantity"))

        domain = [
            ("product_id", "=", self.product_id.id),
            ("state", "=", "done"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]
        if self.location_id:
            domain = [
                "|",
                ("location_id", "=", self.location_id.id),
                ("location_dest_id", "=", self.location_id.id),
            ] + domain
        else:
            domain = [
                "|",
                ("location_id.usage", "in", ("internal", "transit")),
                ("location_dest_id.usage", "in", ("internal", "transit")),
            ] + domain

        move_lines = self.env["stock.move.line"].search(domain, order="date, id")

        lines_vals = []
        for line in move_lines:
            is_in = self._is_in_move(line)
            is_out = self._is_out_move(line)
            if not is_in and not is_out:
                continue

            qty = line.quantity
            if line.product_uom_id and line.product_id.uom_id and line.product_uom_id != line.product_id.uom_id:
                qty = line.product_uom_id._compute_quantity(
                    qty, line.product_id.uom_id, rounding_method="HALF-UP"
                )

            qty_in = qty if is_in else 0.0
            qty_out = qty if is_out else 0.0
            balance += qty_in - qty_out

            move = line.move_id
            picking = line.picking_id or move.picking_id
            reference = picking.name if picking else (move.reference or move.name or "")
            origin = move.origin or ""

            lines_vals.append({
                "wizard_id": self.id,
                "date": line.date,
                "reference": reference,
                "origin": origin,
                "picking_type_id": move.picking_type_id.id,
                "location_id": line.location_id.id,
                "location_dest_id": line.location_dest_id.id,
                "qty_in": qty_in,
                "qty_out": qty_out,
                "balance": balance,
                "reserved_qty": current_reserved,
                "product_uom_id": line.product_id.uom_id.id,
                "move_id": move.id,
            })

        if lines_vals:
            self.env["stock.kardex.report.line"].create(lines_vals)

        return {
            "type": "ir.actions.act_window",
            "name": _("Kardex: %s") % self.product_id.display_name,
            "res_model": "stock.kardex.report.line",
            "view_mode": "list",
            "domain": [("wizard_id", "=", self.id)],
            "target": "current",
            "context": {"create": False, "edit": False, "delete": False},
        }

    def action_print_pdf(self):
        self.ensure_one()
        self.action_generate()
        return self.env.ref("sng_stock_kardex_report.action_report_stock_kardex").report_action(self)
