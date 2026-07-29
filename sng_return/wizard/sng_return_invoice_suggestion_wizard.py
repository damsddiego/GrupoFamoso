"""Comparador de facturas candidatas para una linea de devolucion.

Muestra el ranking calculado en ``sng.return.line._score_invoice_candidates``
con el puntaje y el motivo de cada candidata, y permite al Gerente de
Devoluciones fijar la factura de origen con un clic.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SngReturnInvoiceSuggestionWizard(models.TransientModel):
    _name = "sng.return.invoice.suggestion.wizard"
    _description = "Sugerencia de factura de origen"

    return_line_id = fields.Many2one(
        "sng.return.line",
        string="Linea de devolucion",
        required=True,
        ondelete="cascade",
    )
    return_id = fields.Many2one(
        "sng.return",
        string="Devolucion",
        related="return_line_id.return_id",
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="return_line_id.partner_id",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        related="return_line_id.product_id",
        readonly=True,
    )
    quantity = fields.Float(
        string="Cantidad a devolver",
        related="return_line_id.quantity",
        readonly=True,
    )
    current_invoice_id = fields.Many2one(
        "account.move",
        string="Factura actual",
        related="return_line_id.invoice_id",
        readonly=True,
    )
    suggested_invoice_id = fields.Many2one(
        "account.move",
        string="Factura sugerida",
        related="return_line_id.suggested_invoice_id",
        readonly=True,
    )
    suggestion_confidence = fields.Selection(
        related="return_line_id.suggestion_confidence",
        string="Confianza",
        readonly=True,
    )
    suggestion_reason = fields.Text(
        related="return_line_id.suggestion_reason",
        string="Motivo",
        readonly=True,
    )
    candidate_ids = fields.One2many(
        "sng.return.invoice.suggestion.wizard.line",
        "wizard_id",
        string="Facturas candidatas",
    )
    info_message = fields.Text(string="Mensaje", readonly=True)
    suggestion_source = fields.Selection(
        related="return_line_id.suggestion_source",
        string="Origen",
        readonly=True,
    )
    ia_available = fields.Boolean(
        string="IA disponible",
        compute="_compute_ia_available",
    )

    def _compute_ia_available(self):
        available = self.env["sng.return.line"]._ia_disponible()
        for wizard in self:
            wizard.ia_available = available

    @api.model
    def _build_candidate_commands(self, results):
        commands = []
        for rank, item in enumerate(results, start=1):
            invoice = item["invoice"]
            commands.append((0, 0, {
                "invoice_id": invoice.id,
                "invoice_date": invoice.invoice_date or invoice.date,
                "days_elapsed": item["days"] if item["days"] is not None else 0,
                "invoiced_qty": item["invoiced"],
                "available_qty": item["available"],
                "score": item["score"],
                "eligible": item["eligible"],
                "rank": rank,
                "reason": "\n".join("• %s" % reason for reason in item["reasons"]),
                "currency_id": invoice.currency_id.id,
                "amount_total": invoice.amount_total,
            }))
        return commands

    @api.model
    def _build_info_message(self, line, results):
        if not results:
            return _(
                "No se encontro ninguna factura publicada del cliente %(partner)s que "
                "contenga el producto %(product)s."
            ) % {
                "partner": line.partner_id.display_name,
                "product": line.product_id.display_name,
            }
        eligible = [item for item in results if item["eligible"]]
        if not eligible:
            return _(
                "Se encontraron %(total)s factura(s) con el producto, pero ninguna tiene "
                "disponible suficiente para devolver %(qty)s. Revise devoluciones o notas "
                "de credito previas."
            ) % {"total": len(results), "qty": line.quantity}
        message = _(
            "%(eligible)s de %(total)s factura(s) candidatas tienen disponible suficiente. "
            "El puntaje combina trazabilidad de lote, fecha, cantidad, contexto de venta y "
            "estado de pago."
        ) % {"eligible": len(eligible), "total": len(results)}
        limit = line._suggestion_params()["candidate_limit"]
        if len(results) >= limit:
            message += " " + _(
                "Solo se evaluaron las %(limit)s facturas mas recientes con este producto."
            ) % {"limit": limit}
        return message

    def action_recompute(self):
        self.ensure_one()
        results = self.return_line_id._score_invoice_candidates()
        self.return_line_id._apply_suggestion(results)
        self.candidate_ids.unlink()
        self.write({
            "candidate_ids": self._build_candidate_commands(results),
            "info_message": self._build_info_message(self.return_line_id, results),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_consult_ia(self):
        """Pide a la IA que elija entre las candidatas y recarga el comparador."""
        self.ensure_one()
        self.return_line_id.action_suggest_invoice_ia()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_accept_suggestion(self):
        self.ensure_one()
        self.return_line_id.action_accept_suggestion()
        return {"type": "ir.actions.act_window_close"}


class SngReturnInvoiceSuggestionWizardLine(models.TransientModel):
    _name = "sng.return.invoice.suggestion.wizard.line"
    _description = "Factura candidata de la devolucion"
    _order = "rank, id"

    wizard_id = fields.Many2one(
        "sng.return.invoice.suggestion.wizard",
        required=True,
        ondelete="cascade",
    )
    rank = fields.Integer(string="#")
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
    )
    invoice_date = fields.Date(string="Fecha")
    days_elapsed = fields.Integer(string="Dias")
    invoiced_qty = fields.Float(
        string="Facturado",
        digits="Product Unit of Measure",
    )
    available_qty = fields.Float(
        string="Disponible",
        digits="Product Unit of Measure",
    )
    score = fields.Float(string="Puntaje", digits=(5, 1))
    eligible = fields.Boolean(string="Elegible")
    reason = fields.Text(string="Motivo")
    amount_total = fields.Monetary(
        string="Total factura",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one("res.currency", string="Moneda")
    payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Estado de pago",
        readonly=True,
    )

    def action_select_invoice(self):
        self.ensure_one()
        if not self.eligible:
            raise UserError(_(
                "La factura %(invoice)s no tiene disponible suficiente para esta "
                "devolucion."
            ) % {"invoice": self.invoice_id.display_name})
        self.wizard_id.return_line_id.invoice_id = self.invoice_id.id
        return {"type": "ir.actions.act_window_close"}

    def action_open_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "new",
        }
