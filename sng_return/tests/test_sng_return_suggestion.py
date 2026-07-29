import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    stop_reason = "end_turn"

    def __init__(self, payload):
        self.content = [_FakeTextBlock(json.dumps(payload))]


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._payload)


class _FakeClient:
    def __init__(self, payload):
        self.messages = _FakeMessages(payload)


class TestSngReturnSuggestion(TransactionCase):
    """Sugerencia de la factura de origen de una linea de devolucion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({
            "groups_id": [(4, cls.env.ref("sng_return.group_sng_return_manager").id)]
        })
        cls.company.payment_method_default_id = cls.env.ref(
            "cr_electronic_invoice.PaymentMethods_1"
        )
        cls.income_account = cls.env["account.account"].create({
            "name": "Ingresos sugerencia",
            "code": "TSTSUGI",
            "account_type": "income",
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.receivable_account = cls.env["account.account"].create({
            "name": "Por cobrar sugerencia",
            "code": "TSTSUGR",
            "account_type": "asset_receivable",
            "reconcile": True,
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.env["account.journal"].create({
            "name": "Ventas sugerencia",
            "code": "TSUG",
            "type": "sale",
            "company_id": cls.company.id,
            "default_account_id": cls.income_account.id,
        })
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente sugerencia",
            "customer_rank": 1,
            "property_account_receivable_id": cls.receivable_account.id,
        })
        cls.product = cls._create_product("Producto sugerido")
        cls.other_product = cls._create_product("Producto de una sola factura")
        cls.reason = cls.env["sng.return.reason"].create({
            "name": "Motivo sugerencia",
        })

        today = fields.Date.context_today(cls.env.user)
        cls.old_date = today - timedelta(days=120)
        cls.recent_date = today

        # La factura antigua se emite primero para no romper la cronologia de
        # la secuencia del diario.
        cls.old_invoice = cls._create_posted_invoice(
            [(cls.product, 5.0)], cls.old_date
        )
        cls.recent_invoice = cls._create_posted_invoice(
            [(cls.product, 5.0), (cls.other_product, 3.0)], cls.recent_date
        )

    @classmethod
    def _create_product(cls, name):
        product = cls.env["product.product"].create({
            "name": name,
            "is_storable": True,
            "list_price": 100.0,
            "invoice_policy": "order",
            "property_account_income_id": cls.income_account.id,
        })
        template = product.product_tmpl_id
        if "cabys_product_id" in template._fields:
            template.cabys_product_id = cls.env["cabys.producto"].search([], limit=1)
        if not product.cabys_code and not template._fields["cabys_code"].related:
            template.cabys_code = "8399000000000"
        cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": product.id,
            "location_id": cls.warehouse.lot_stock_id.id,
            "inventory_quantity": 100.0,
        }).action_apply_inventory()
        return product

    @classmethod
    def _create_posted_invoice(cls, product_quantities, invoice_date):
        order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "warehouse_id": cls.warehouse.id,
            "order_line": [
                (0, 0, {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "price_unit": 100.0,
                })
                for product, qty in product_quantities
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.invoice_date = invoice_date
        invoice.action_post()
        return invoice

    def _create_return(self, product=None, quantity=1.0, notes=False):
        return self.env["sng.return"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "reason_id": self.reason.id,
            "notes": notes,
            "line_ids": [(0, 0, {
                "product_id": (product or self.product).id,
                "quantity": quantity,
            })],
        })

    # ------------------------------------------------------------------
    def test_recent_invoice_ranks_first(self):
        line = self._create_return(quantity=2.0).line_ids
        results = line._score_invoice_candidates()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["invoice"], self.recent_invoice)
        self.assertTrue(all(item["eligible"] for item in results))
        self.assertGreater(results[0]["score"], results[1]["score"])

        best = line._apply_suggestion(results)
        self.assertEqual(line.suggested_invoice_id, self.recent_invoice)
        self.assertEqual(line.suggestion_source, "heuristic")
        self.assertEqual(best["invoice"], self.recent_invoice)
        self.assertTrue(line.suggestion_reason)

    def test_exhausted_invoice_is_not_eligible(self):
        # Una devolucion confirmada consume todo el disponible de la factura
        # reciente, por lo que deja de ser candidata.
        previous = self._create_return(quantity=5.0)
        previous.line_ids.invoice_id = self.recent_invoice
        previous._confirm_with_warehouse(self.warehouse)
        # En uso real la devolución previa vive en otra transacción; sin este
        # flush el cómputo de métricas de la nueva línea reentra en la anterior.
        self.env.flush_all()
        self.env.invalidate_all()

        line = self._create_return(quantity=2.0).line_ids
        results = line._score_invoice_candidates()

        by_invoice = {item["invoice"]: item for item in results}
        self.assertFalse(by_invoice[self.recent_invoice]["eligible"])
        self.assertEqual(by_invoice[self.recent_invoice]["available"], 0.0)
        self.assertTrue(by_invoice[self.old_invoice]["eligible"])

        line._apply_suggestion(results)
        self.assertEqual(line.suggested_invoice_id, self.old_invoice)

    def test_invoice_mentioned_in_notes_wins(self):
        notes = "El cliente devuelve contra la factura %s" % self.old_invoice.name
        line = self._create_return(quantity=2.0, notes=notes).line_ids
        results = line._score_invoice_candidates()

        self.assertEqual(results[0]["invoice"], self.old_invoice)
        self.assertIn(
            "notas",
            " ".join(results[0]["reasons"]).lower(),
        )

    def test_single_candidate_is_assigned_automatically(self):
        customer_return = self._create_return(product=self.other_product, quantity=1.0)

        customer_return.action_suggest_invoices()

        line = customer_return.line_ids
        self.assertEqual(line.suggestion_confidence, "high")
        self.assertEqual(line.suggested_invoice_id, self.recent_invoice)
        self.assertEqual(line.invoice_id, self.recent_invoice)
        self.assertTrue(line.suggestion_matches_invoice)
        self.assertEqual(customer_return.suggestion_pending_count, 0)

    def test_suggestion_is_cleared_when_quantity_changes(self):
        line = self._create_return(quantity=2.0).line_ids
        line._apply_suggestion()
        self.assertTrue(line.suggested_invoice_id)

        line.quantity = 3.0

        self.assertFalse(line.suggested_invoice_id)
        self.assertFalse(line.suggestion_confidence)
        self.assertEqual(line.suggestion_score, 0.0)

    def test_wizard_lists_candidates_and_sets_invoice(self):
        line = self._create_return(quantity=2.0).line_ids

        action = line.action_suggest_invoice()
        wizard = self.env[action["res_model"]].browse(action["res_id"])

        self.assertEqual(len(wizard.candidate_ids), 2)
        self.assertEqual(wizard.candidate_ids[0].rank, 1)
        self.assertEqual(wizard.candidate_ids[0].invoice_id, self.recent_invoice)
        self.assertEqual(wizard.suggested_invoice_id, self.recent_invoice)

        old_candidate = wizard.candidate_ids.filtered(
            lambda candidate: candidate.invoice_id == self.old_invoice
        )
        old_candidate.action_select_invoice()

        self.assertEqual(line.invoice_id, self.old_invoice)
        self.assertFalse(line.suggestion_matches_invoice)

    # ------------------------------------------------------------------
    # Capa de IA
    # ------------------------------------------------------------------
    def _patch_ia(self, payload):
        client = _FakeClient(payload)
        params = {"model": "claude-opus-5", "effort": "low"}
        return client, patch.object(
            type(self.env["sng.return.line"]),
            "_ia_get_client",
            lambda self: (client, params),
        )

    def test_ia_is_not_consulted_when_disabled(self):
        line = self._create_return(quantity=2.0).line_ids
        self.assertFalse(self.env["sng.return.line"]._ia_disponible())
        results = line._score_invoice_candidates()
        self.assertFalse(line._ia_debe_consultar(results, "low"))

        with patch.object(
            type(self.env["sng.return.line"]), "_ia_consultar"
        ) as consulta:
            line._apply_suggestion(results)

        self.assertFalse(consulta.called)
        self.assertEqual(line.suggestion_source, "heuristic")

    def test_ia_choice_overrides_heuristic(self):
        line = self._create_return(quantity=2.0).line_ids
        client, patcher = self._patch_ia({
            "factura_id": self.old_invoice.id,
            "confianza": "alta",
            "motivo": "El cliente indica que la compra fue en la temporada anterior",
        })
        results = line._score_invoice_candidates()
        with patcher:
            elegida = line._ia_consultar(results)

        self.assertEqual(elegida["invoice"], self.old_invoice)
        payload = json.loads(client.messages.last_kwargs["messages"][0]["content"])
        self.assertEqual(
            {c["factura_id"] for c in payload["candidatas"]},
            {self.old_invoice.id, self.recent_invoice.id},
        )

    def test_ia_cannot_pick_invoice_outside_candidates(self):
        line = self._create_return(quantity=2.0).line_ids
        results = line._score_invoice_candidates()
        # Una factura de otro cliente: jamas debe poder elegirse.
        intruder = self.env["account.move"].search(
            [("id", "not in", [self.old_invoice.id, self.recent_invoice.id])],
            limit=1,
        )
        _client, patcher = self._patch_ia({
            "factura_id": intruder.id if intruder else 999999,
            "confianza": "alta",
            "motivo": "Respuesta fuera de la lista cerrada",
        })
        with patcher:
            self.assertIsNone(line._ia_consultar(results))

    def test_ia_failure_keeps_heuristic_suggestion(self):
        line = self._create_return(quantity=2.0).line_ids
        with patch.object(
            type(self.env["sng.return.line"]),
            "_ia_debe_consultar",
            lambda self, results, confidence: True,
        ), patch.object(
            type(self.env["sng.return.line"]),
            "_ia_consultar",
            side_effect=RuntimeError("sin conexion"),
        ):
            best = line._apply_suggestion()

        self.assertEqual(best["invoice"], self.recent_invoice)
        self.assertEqual(line.suggested_invoice_id, self.recent_invoice)
        self.assertIn("fallo", line.suggestion_reason.lower())

    def test_suggestion_can_be_refreshed_on_confirmed_line(self):
        customer_return = self._create_return(quantity=2.0)
        customer_return.line_ids.invoice_id = self.recent_invoice
        customer_return._confirm_with_warehouse(self.warehouse)

        # Sobre una linea confirmada la sugerencia se puede recalcular sin
        # tropezar con la restriccion de edicion.
        customer_return.line_ids._apply_suggestion()

        self.assertTrue(customer_return.line_ids.suggested_invoice_id)
        self.assertEqual(customer_return.line_ids.invoice_id, self.recent_invoice)
