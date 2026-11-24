# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAssetsTablero(TransactionCase):
    """El parche del clic en la gráfica debe cargarse en el paquete de
    hojas de cálculo que usan los tableros."""

    def test_parche_clic_grafica_en_bundle_de_tableros(self):
        rutas = self.env["ir.asset"]._get_asset_paths(
            bundle="spreadsheet.o_spreadsheet", assets_params={}
        )
        archivo = "sng_invoice_report_salesperson/static/src/bundle/clic_grafica_periodo.js"
        self.assertTrue(
            any(archivo in str(ruta) for ruta in rutas),
            "clic_grafica_periodo.js no está en spreadsheet.o_spreadsheet",
        )
