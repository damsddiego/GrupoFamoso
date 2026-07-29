"""Sugerencia de la factura de origen de una linea de devolucion.

El objetivo es que el Gerente de Devoluciones no tenga que buscar a mano contra
que factura se acredita cada producto. El modulo puntua las facturas candidatas
del cliente con criterios deterministas y explicables; la asignacion definitiva
del campo ``invoice_id`` sigue siendo una decision del gerente salvo que la
sugerencia sea de confianza alta.

Los pesos suman 100 y estan expresados como constantes para poder afinarlos sin
tocar la logica. La referencia textual es un bono aparte porque, cuando el
cliente indica el numero de factura, es practicamente concluyente.
"""

import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape
from odoo.tools.float_utils import float_compare, float_is_zero

# Pesos de los criterios (suman 100).
W_TRACEABILITY = 30.0   # lote/serie recibido rastreado hasta la factura
W_RECENCY = 25.0        # cercania a la ventana de devolucion
W_QUANTITY = 20.0       # coincidencia de cantidades
W_CONTEXT = 15.0        # almacen y vendedor de la orden de origen
W_PAYMENT = 10.0        # estado de pago de la factura

# Bono por mencion explicita del numero de factura en las notas.
BONUS_TEXT_REFERENCE = 25.0

# Preferencia por estado de pago: se acredita antes contra lo que el cliente
# aun debe que contra una factura ya cobrada.
PAYMENT_STATE_FACTOR = {
    "not_paid": 1.0,
    "blocked": 0.7,
    "partial": 0.6,
    "in_payment": 0.4,
    "paid": 0.3,
    "reversed": 0.0,
}

CONFIDENCE_LABELS = {
    "high": "alta",
    "medium": "media",
    "low": "baja",
}

_NON_ALNUM = re.compile(r"[^0-9A-Z]")


def _normalize_reference(text):
    """Deja solo mayusculas y digitos para comparar numeros de documento."""
    return _NON_ALNUM.sub("", (text or "").upper())


class SngReturnLine(models.Model):
    _inherit = "sng.return.line"

    suggested_invoice_id = fields.Many2one(
        "account.move",
        string="Factura sugerida",
        copy=False,
        readonly=True,
        help="Factura de origen propuesta automaticamente segun los criterios de "
             "trazabilidad, fecha, cantidad, contexto de venta y estado de pago.",
    )
    suggestion_score = fields.Float(
        string="Puntaje",
        copy=False,
        readonly=True,
        digits=(5, 1),
        help="Puntaje de 0 a 100 de la factura sugerida.",
    )
    suggestion_confidence = fields.Selection(
        [
            ("high", "Alta"),
            ("medium", "Media"),
            ("low", "Baja"),
        ],
        string="Confianza",
        copy=False,
        readonly=True,
    )
    suggestion_reason = fields.Text(
        string="Motivo de la sugerencia",
        copy=False,
        readonly=True,
    )
    suggestion_source = fields.Selection(
        [
            ("heuristic", "Criterios"),
            ("ai", "IA"),
        ],
        string="Origen de la sugerencia",
        copy=False,
        readonly=True,
    )
    suggestion_date = fields.Datetime(
        string="Fecha de la sugerencia",
        copy=False,
        readonly=True,
    )
    suggestion_matches_invoice = fields.Boolean(
        string="Sugerencia aplicada",
        compute="_compute_suggestion_matches_invoice",
    )

    @api.depends("invoice_id", "suggested_invoice_id")
    def _compute_suggestion_matches_invoice(self):
        for line in self:
            line.suggestion_matches_invoice = bool(
                line.suggested_invoice_id
                and line.suggested_invoice_id == line.invoice_id
            )

    # ------------------------------------------------------------------
    # Parametros
    # ------------------------------------------------------------------
    @api.model
    def _suggestion_params(self):
        icp = self.env["ir.config_parameter"].sudo()

        def _num(key, default):
            try:
                return float(icp.get_param(key) or default)
            except (TypeError, ValueError):
                return float(default)

        return {
            # Ventana de devolucion habitual del negocio, en dias.
            "window_days": max(1.0, _num("sng_return.suggestion_window_days", 60)),
            # Puntaje minimo para considerar la sugerencia de confianza alta.
            "min_score": _num("sng_return.suggestion_min_score", 70),
            # Ventaja minima sobre la segunda candidata para confianza alta.
            "min_margin": _num("sng_return.suggestion_min_margin", 20),
            "candidate_limit": max(1, int(_num("sng_return.suggestion_candidate_limit", 30))),
        }

    # ------------------------------------------------------------------
    # Candidatas y senales
    # ------------------------------------------------------------------
    def _get_invoice_candidates(self):
        """Facturas del cliente que contienen el producto a devolver.

        El dominio replica el del campo ``invoice_id`` para garantizar que toda
        candidata sugerida sea tambien seleccionable en la interfaz.
        """
        self.ensure_one()
        if not self.product_id or not self.partner_id:
            return self.env["account.move"]
        params = self._suggestion_params()
        return self.env["account.move"].search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id.id),
                ("partner_id", "child_of", self.partner_id.id),
                ("invoice_line_ids.product_id", "=", self.product_id.id),
            ],
            order="invoice_date desc, id desc",
            limit=params["candidate_limit"],
        )

    def _get_traced_invoice_ids(self):
        """Facturas alcanzables desde los lotes/series recibidos en la devolucion.

        Es la senal mas fuerte: si el lote que entro por la recepcion salio en un
        albaran ligado a una orden facturada, esa factura es la correcta.
        """
        self.ensure_one()
        if not self.product_id or self.product_id.tracking == "none":
            return set()
        moves = self.return_id.picking_ids.move_ids.filtered(
            lambda move: move.product_id == self.product_id and move.state != "cancel"
        )
        lots = moves.move_line_ids.lot_id
        if not lots:
            return set()
        # sudo: es una lectura de trazabilidad para puntuar; el usuario de
        # devoluciones no necesariamente tiene acceso a los movimientos de salida.
        out_move_lines = self.env["stock.move.line"].sudo().search([
            ("lot_id", "in", lots.ids),
            ("state", "=", "done"),
            ("picking_code", "=", "outgoing"),
            ("company_id", "=", self.company_id.id),
        ])
        invoice_lines = out_move_lines.move_id.sale_line_id.invoice_lines
        return set(
            invoice_lines.filtered(
                lambda aml: aml.move_id.move_type == "out_invoice"
                and aml.move_id.state == "posted"
            ).move_id.ids
        )

    def _get_reference_haystack(self):
        """Texto libre donde el cliente o el vendedor pudo anotar la factura."""
        self.ensure_one()
        parts = [self.notes, self.return_id.notes]
        return _normalize_reference(" ".join(part for part in parts if part))

    @api.model
    def _invoice_reference_tokens(self, invoice):
        tokens = [invoice.name, invoice.ref]
        # Consecutivo de Hacienda cuando esta disponible (cr_electronic_invoice).
        if "number_electronic" in invoice._fields:
            tokens.append(invoice.number_electronic)
        normalized = {_normalize_reference(token) for token in tokens if token}
        return {token for token in normalized if len(token) >= 5}

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _score_invoice_candidates(self, candidates=None):
        """Puntua las facturas candidatas y las devuelve ordenadas.

        Cada elemento es un dict con la factura, el puntaje, si es elegible
        (disponible suficiente) y la lista de motivos legibles.
        """
        self.ensure_one()
        if candidates is None:
            candidates = self._get_invoice_candidates()
        if not candidates:
            return []

        params = self._suggestion_params()
        window = params["window_days"]
        maps = self._build_invoice_availability_maps(candidates, [self.product_id.id])
        traced_ids = self._get_traced_invoice_ids()
        haystack = self._get_reference_haystack()
        today = fields.Date.context_today(self)
        rounding = self.uom_id.rounding or 0.01

        results = []
        for invoice in candidates:
            key = (invoice.id, self.product_id.id)
            invoiced = maps["invoiced"].get(key, 0.0)
            returned = maps["returned"].get(key, 0.0)
            # No descontar la propia linea si ya esta confirmada contra esta
            # misma factura: ya viene sumada en el agregado.
            if (
                self.state == "confirmed"
                and isinstance(self.id, int)
                and self.invoice_id == invoice
            ):
                returned = max(0.0, returned - self.quantity)
            credited = maps["credited"].get(key, 0.0)
            available = max(0.0, invoiced - returned - credited)
            eligible = float_compare(
                available, self.quantity, precision_rounding=rounding
            ) >= 0

            reasons = []
            score = 0.0

            # 1. Trazabilidad por lote/serie.
            if invoice.id in traced_ids:
                score += W_TRACEABILITY
                reasons.append(_("El lote/serie recibido se rastrea hasta esta factura"))

            # 2. Recencia respecto a la ventana de devolucion.
            invoice_date = invoice.invoice_date or invoice.date
            days = (today - invoice_date).days if invoice_date else None
            if days is None:
                recency = 0.0
            elif days <= 0:
                recency = W_RECENCY
            elif days <= window:
                recency = W_RECENCY * (1.0 - 0.4 * days / window)
            elif days <= 3 * window:
                recency = W_RECENCY * 0.6 * (1.0 - (days - window) / (2.0 * window))
            else:
                recency = 0.0
            score += recency
            if days is None:
                reasons.append(_("La factura no tiene fecha registrada"))
            elif days <= window:
                reasons.append(_(
                    "Facturada hace %(days)s dia(s), dentro de la ventana de %(window)s"
                ) % {"days": max(days, 0), "window": int(window)})
            else:
                reasons.append(_(
                    "Facturada hace %(days)s dia(s), fuera de la ventana de %(window)s"
                ) % {"days": days, "window": int(window)})

            # 3. Coincidencia de cantidades.
            line_qtys = []
            for inv_line in invoice.invoice_line_ids:
                if inv_line.display_type != "product" or inv_line.product_id != self.product_id:
                    continue
                qty = inv_line.quantity
                if inv_line.product_uom_id:
                    qty = inv_line.product_uom_id._compute_quantity(
                        qty, self.product_id.uom_id
                    )
                line_qtys.append(qty)
            exact_line = any(
                float_is_zero(qty - self.quantity, precision_rounding=rounding)
                for qty in line_qtys
            )
            if exact_line:
                score += W_QUANTITY
                reasons.append(_(
                    "Una linea de la factura tiene exactamente la cantidad a devolver"
                ))
            elif eligible and float_is_zero(
                available - self.quantity, precision_rounding=rounding
            ):
                score += W_QUANTITY * 0.8
                reasons.append(_("El disponible de la factura calza exacto con la devolucion"))
            elif eligible:
                score += W_QUANTITY * 0.4

            # 4. Contexto de la venta: almacen y vendedor.
            orders = self.env["sale.order"].browse(sorted(maps["orders"].get(key, ())))
            warehouse = self.return_id.warehouse_id
            if warehouse and warehouse in orders.warehouse_id:
                score += W_CONTEXT * 0.6
                reasons.append(_("Se despacho desde el mismo almacen de la devolucion"))
            if self.return_id.user_id and self.return_id.user_id in orders.user_id:
                score += W_CONTEXT * 0.4
                reasons.append(_("Mismo vendedor responsable de la devolucion"))

            # 5. Estado de pago.
            score += W_PAYMENT * PAYMENT_STATE_FACTOR.get(invoice.payment_state, 0.3)
            if invoice.payment_state in ("not_paid", "partial"):
                reasons.append(_("La factura aun tiene saldo pendiente"))

            # Bono: el numero de factura aparece en las notas.
            if haystack and any(
                token in haystack for token in self._invoice_reference_tokens(invoice)
            ):
                score += BONUS_TEXT_REFERENCE
                reasons.append(_("El numero de esta factura aparece en las notas"))

            score = min(100.0, score)
            if not eligible:
                score = 0.0
                reasons = [
                    _(
                        "Disponible insuficiente: %(available)s frente a %(qty)s a devolver"
                    ) % {"available": available, "qty": self.quantity}
                ]

            results.append({
                "invoice": invoice,
                "score": round(score, 1),
                "eligible": eligible,
                "available": available,
                "invoiced": invoiced,
                "days": days,
                "reasons": reasons,
            })

        results.sort(
            key=lambda item: (
                item["eligible"],
                item["score"],
                item["invoice"].invoice_date or fields.Date.today(),
            ),
            reverse=True,
        )
        return results

    @api.model
    def _confidence_from_results(self, results):
        """Confianza de la mejor candidata segun puntaje y ventaja sobre la segunda.

        Con una sola factura elegible no hay ambiguedad que resolver: el puntaje
        mide que tan buena es la coincidencia, no cuantas alternativas hay. Con
        dos o mas se exige puntaje minimo y ventaja clara sobre la segunda.
        """
        eligible = [item for item in results if item["eligible"]]
        if not eligible:
            return None, 0.0
        params = self._suggestion_params()
        best = eligible[0]
        if len(eligible) == 1:
            return "high", best["score"]
        margin = best["score"] - eligible[1]["score"]
        if best["score"] >= params["min_score"] and margin >= params["min_margin"]:
            return "high", margin
        if best["score"] >= 50 or margin >= params["min_margin"]:
            return "medium", margin
        return "low", margin

    def _clear_suggestion(self, reason=False):
        self.ensure_one()
        self.write({
            "suggested_invoice_id": False,
            "suggestion_score": 0.0,
            "suggestion_confidence": False,
            "suggestion_reason": reason,
            "suggestion_source": False,
            "suggestion_date": fields.Datetime.now() if reason else False,
        })

    def _apply_suggestion(self, results=None, source="heuristic"):
        """Guarda la mejor candidata en los campos de sugerencia.

        Devuelve el dict de la candidata elegida (con ``confidence``) o None si
        no hay ninguna elegible.
        """
        self.ensure_one()
        if results is None:
            results = self._score_invoice_candidates()
        confidence, margin = self._confidence_from_results(results)
        if not confidence:
            self._clear_suggestion(reason=_(
                "No se encontro ninguna factura del cliente con disponible "
                "suficiente para este producto."
            ))
            return None
        best = [item for item in results if item["eligible"]][0]
        self.write({
            "suggested_invoice_id": best["invoice"].id,
            "suggestion_score": best["score"],
            "suggestion_confidence": confidence,
            "suggestion_reason": "\n".join("• %s" % reason for reason in best["reasons"]),
            "suggestion_source": source,
            "suggestion_date": fields.Datetime.now(),
        })
        return dict(best, confidence=confidence, margin=margin)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_suggest_invoice(self):
        """Calcula el ranking y abre el comparador de facturas candidatas."""
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Debe seleccionar un producto antes de sugerir la factura."))
        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente antes de sugerir la factura."))
        results = self._score_invoice_candidates()
        self._apply_suggestion(results)
        wizard_model = self.env["sng.return.invoice.suggestion.wizard"]
        wizard = wizard_model.create({
            "return_line_id": self.id,
            "candidate_ids": wizard_model._build_candidate_commands(results),
            "info_message": wizard_model._build_info_message(self, results),
        })
        return {
            "name": _("Sugerencia de factura de origen"),
            "type": "ir.actions.act_window",
            "res_model": "sng.return.invoice.suggestion.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_accept_suggestion(self):
        """Copia la factura sugerida al campo de factura de origen."""
        self.ensure_one()
        if not self.suggested_invoice_id:
            raise UserError(_("Esta linea no tiene una factura sugerida."))
        self.invoice_id = self.suggested_invoice_id.id
        return True


class SngReturn(models.Model):
    _inherit = "sng.return"

    suggestion_pending_count = fields.Integer(
        string="Lineas sin factura",
        compute="_compute_suggestion_pending_count",
    )

    @api.depends("line_ids.invoice_id")
    def _compute_suggestion_pending_count(self):
        for record in self:
            record.suggestion_pending_count = len(
                record.line_ids.filtered(lambda line: not line.invoice_id)
            )

    def action_suggest_invoices(self):
        """Sugiere la factura de origen de todas las lineas que no la tienen.

        Las sugerencias de confianza alta se asignan solas cuando quien ejecuta
        es Gerente de Devoluciones y la devolucion no tiene notas de credito
        activas; el resto queda propuesto para revision manual.
        """
        self.ensure_one()
        pending = self.line_ids.filtered(lambda line: not line.invoice_id and line.product_id)
        if not pending:
            raise UserError(_("Todas las lineas ya tienen una factura de origen asignada."))

        can_assign = (
            self.env.user.has_group("sng_return.group_sng_return_manager")
            and not self._get_active_credit_notes()
        )

        assigned, proposed, empty = [], [], []
        for line in pending:
            best = line._apply_suggestion()
            if not best:
                empty.append(line)
            elif can_assign and best["confidence"] == "high":
                line.invoice_id = best["invoice"].id
                assigned.append((line, best))
            else:
                proposed.append((line, best))

        self._post_suggestion_summary(assigned, proposed, empty)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if assigned else "warning",
                "title": _("Sugerencia de facturas"),
                "message": _(
                    "%(assigned)s asignada(s) automaticamente, %(proposed)s propuesta(s) "
                    "para revision y %(empty)s sin candidata."
                ) % {
                    "assigned": len(assigned),
                    "proposed": len(proposed),
                    "empty": len(empty),
                },
                # Recargar para que se vean las facturas asignadas automaticamente.
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _post_suggestion_summary(self, assigned, proposed, empty):
        """Deja la traza de la sugerencia en el chatter, con puntaje y motivo."""
        self.ensure_one()
        rows = []
        for line, best in assigned:
            rows.append(_(
                "%(product)s → %(invoice)s (%(score)s pts, confianza alta): asignada automaticamente"
            ) % {
                "product": line.product_id.display_name,
                "invoice": best["invoice"].display_name,
                "score": best["score"],
            })
        for line, best in proposed:
            rows.append(_(
                "%(product)s → %(invoice)s (%(score)s pts, confianza %(confidence)s): "
                "requiere confirmacion"
            ) % {
                "product": line.product_id.display_name,
                "invoice": best["invoice"].display_name,
                "score": best["score"],
                "confidence": CONFIDENCE_LABELS.get(best["confidence"], best["confidence"]),
            })
        for line in empty:
            rows.append(_(
                "%(product)s: sin factura candidata con disponible suficiente"
            ) % {"product": line.product_id.display_name})

        if not rows:
            return
        body = Markup("<p>%s</p><ul>%s</ul>") % (
            _("Sugerencia de factura de origen:"),
            Markup("").join(Markup("<li>%s</li>") % html_escape(row) for row in rows),
        )
        self.message_post(body=body)
