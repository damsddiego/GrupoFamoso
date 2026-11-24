# -*- coding: utf-8 -*-
import json

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInvoiceReportSalesperson(TransactionCase):
    """El vendedor real de la factura (contacto de sales_commission_omax)
    debe verse en Análisis de facturas (account.invoice.report)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.vendedor = Partner.create({
            "name": "Vendedor prueba reporte",
            "is_salesperson": True,
        })
        cls.cliente = Partner.create({"name": "Cliente prueba reporte"})
        cls.producto = cls.env["product.product"].create({
            "name": "Producto prueba reporte",
            "type": "service",
            "list_price": 100.0,
        })

    def _crear_factura(self, vendedor):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.cliente.id,
            "salesperson_id": vendedor.id if vendedor else False,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.producto.id,
                "quantity": 2,
                "price_unit": 100.0,
                "tax_ids": [(5, 0, 0)],
            })],
        })

    def _lineas_reporte(self, factura):
        return self.env["account.invoice.report"].search(
            [("move_id", "=", factura.id)]
        )

    def test_reporte_muestra_vendedor_de_la_factura(self):
        factura = self._crear_factura(self.vendedor)
        lineas = self._lineas_reporte(factura)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas.salesperson_id, self.vendedor)

    def test_reporte_sin_vendedor_queda_vacio(self):
        factura = self._crear_factura(False)
        # El compute de omax rellena con el partner del usuario; lo vaciamos
        # para cubrir las facturas históricas sin vendedor.
        factura.salesperson_id = False
        lineas = self._lineas_reporte(factura)
        self.assertEqual(len(lineas), 1)
        self.assertFalse(lineas.salesperson_id)

    def test_reporte_agrupa_por_vendedor(self):
        factura = self._crear_factura(self.vendedor)
        grupos = self.env["account.invoice.report"].read_group(
            [("move_id", "=", factura.id)],
            ["price_subtotal:sum"],
            ["salesperson_id"],
        )
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["salesperson_id"][0], self.vendedor.id)
        self.assertAlmostEqual(grupos[0]["price_subtotal"], 200.0)


@tagged("post_install", "-at_install")
class TestTableroFacturacion(TransactionCase):
    """El tablero Tableros > Facturación debe filtrar y agrupar por el
    vendedor contacto (salesperson_id) y no por el usuario de Odoo."""

    FILTRO_VENDEDOR = "02acc7f7-b282-4ce9-bf38-6abfb72be6aa"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tablero = cls.env.ref("spreadsheet_dashboard_account.dashboard_invoicing")
        cls.datos = json.loads(cls.tablero.spreadsheet_data)

    def test_tablero_no_usa_usuario_de_odoo(self):
        texto = json.dumps(self.datos)
        self.assertNotIn("invoice_user_id", texto)
        self.assertNotIn("res.users", texto)

    def test_filtro_vendedor_es_contacto_vendedor(self):
        filtro = next(
            f for f in self.datos["globalFilters"] if f["id"] == self.FILTRO_VENDEDOR
        )
        self.assertEqual(filtro["modelName"], "res.partner")
        self.assertEqual(filtro["domainOfAllowedValues"], [["is_salesperson", "=", True]])

    def test_tabla_vendedores_agrupa_por_salesperson(self):
        pivote = self.datos["pivots"]["4"]
        self.assertEqual(pivote["rows"], [{"fieldName": "salesperson_id"}])
        self.assertIn(["salesperson_id", "!=", False], pivote["domain"])
        for pivote in self.datos["pivots"].values():
            self.assertEqual(
                pivote["fieldMatching"][self.FILTRO_VENDEDOR]["chain"], "salesperson_id"
            )

    def test_tablero_se_puede_abrir(self):
        resultado = self.tablero.get_readonly_dashboard()
        self.assertIn("snapshot", resultado)
        self.assertNotIn("invoice_user_id", json.dumps(resultado["snapshot"]))
