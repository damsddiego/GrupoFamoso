# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import ComercialCommon


@tagged('post_install', '-at_install')
class TestInventario(ComercialCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aceite = cls._producto('Aceite inventario 5L', 'COM-INV-1', cls.pilar, cls.base, cls.vol_5)
        cls.sin_pilar = cls._producto('Sin pilar inventario', 'COM-INV-2', volumen=cls.vol_5)
        # Misma referencia interna en la compañía bodega, como GF y SAASA.
        cls.aceite_bodega = cls._producto('Aceite inventario 5L (bodega)', 'COM-INV-1', company=cls.other_company)

    def _poner_stock(self, product, qty, company=None):
        company = company or self.company
        self.env['stock.quant'].with_company(company)._update_available_quantity(
            product, self._stock_location(company), qty)

    def test_stock_y_litros(self):
        self._poner_stock(self.aceite, 40)
        linea = self._inventario(self.aceite)
        self.assertEqual(len(linea), 1)
        self.assertEqual(linea.default_code, 'COM-INV-1')
        self.assertEqual((linea.pilar_id, linea.base_id, linea.volumen_id), (self.pilar, self.base, self.vol_5))
        self.assertEqual((linea.stock, linea.transito, linea.bodega_grupo), (40.0, 0.0, 0.0))
        self.assertEqual((linea.total, linea.total_litros), (40.0, 200.0))

    def test_producto_sin_pilar_no_entra(self):
        self._poner_stock(self.sin_pilar, 10)
        self.assertFalse(self._inventario(self.sin_pilar))

    def test_transito_es_lo_pendiente_de_ordenes_confirmadas(self):
        borrador = self._orden_compra(self.aceite, 50)
        self.assertEqual(self._inventario(self.aceite).transito, 0.0)

        confirmada = self._orden_compra(self.aceite, 30)
        # Estado directo: el flujo de aprobación de compras no es parte de la prueba.
        confirmada.write({'state': 'purchase'})
        self.assertEqual(self._inventario(self.aceite).transito, 30.0)

        self._recibir(self.aceite, 12, '2031-03-10', orden=confirmada)
        self.env.flush_all()
        self.assertEqual(confirmada.order_line.qty_received, 12.0)
        self.assertEqual(self._inventario(self.aceite).transito, 18.0)
        self.assertEqual(borrador.state, 'draft')

    def test_bodega_grupo_por_referencia_interna(self):
        self._poner_stock(self.aceite, 5)
        self._poner_stock(self.aceite_bodega, 700, company=self.other_company)
        # Sin compañía bodega configurada no se suma nada.
        self.company.sng_comercial_bodega_company_id = False
        self.assertEqual(self._inventario(self.aceite).bodega_grupo, 0.0)

        self.company.sng_comercial_bodega_company_id = self.other_company
        linea = self._inventario(self.aceite)
        self.assertEqual((linea.stock, linea.bodega_grupo, linea.total), (5.0, 700.0, 705.0))
        self.assertEqual(linea.total_litros, 3525.0)
