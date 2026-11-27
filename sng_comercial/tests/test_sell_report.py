# -*- coding: utf-8 -*-
from odoo.tests import new_test_user, tagged

from .common import ComercialCommon


@tagged('post_install', '-at_install')
class TestSellReport(ComercialCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aceite = cls._producto('Aceite sell 5L', 'COM-SELL-1', cls.pilar, cls.base, cls.vol_5)
        cls.spray = cls._producto('Spray sell 400ml', 'COM-SELL-2', cls.pilar_b, volumen=cls.vol_400)
        cls.sin_pilar = cls._producto('Sin pilar sell', 'COM-SELL-3', base=cls.base, volumen=cls.vol_5)
        cls.docena = cls.env.ref('uom.product_uom_dozen')

    def test_sell_in_es_lo_recibido_menos_devoluciones(self):
        self._recibir(self.aceite, 100, '2031-03-10')
        self._recibir(self.aceite, 8, '2031-03-20', devolucion=True)
        self.assertEqual(self._totales(self.aceite), (92.0, 0.0, 460.0, 0.0))

        linea = self.Sell.search([('product_id', '=', self.aceite.id), ('cantidad', '>', 0)])
        self.assertEqual(linea.tipo, 'sell_in')
        self.assertEqual(linea.partner_id, self.proveedor)
        self.assertEqual(linea.pilar_id, self.pilar)
        self.assertEqual(linea.base_id, self.base)
        self.assertEqual(linea.volumen_id, self.vol_5)
        self.assertEqual(linea.company_id, self.company)

    def test_sell_in_sin_orden_de_compra_no_cuenta(self):
        move = self._recibir(self.aceite, 10, '2031-03-10')
        self.assertEqual(self._totales(self.aceite)[0], 10.0)
        move.purchase_line_id = False
        self.assertEqual(self._totales(self.aceite)[0], 0.0)

    def test_sell_in_convierte_la_unidad_de_medida(self):
        self._recibir(self.aceite, 2, '2031-03-10', uom=self.docena)
        self.assertEqual(self._totales(self.aceite)[:1], (24.0,))

    def test_mes_de_recepcion_en_hora_de_costa_rica(self):
        move = self._recibir(self.aceite, 5, '2031-03-31')
        # 02:00 UTC del 1 de abril todavía es 31 de marzo en Costa Rica.
        move.date = '2031-04-01 02:00:00'
        self.assertEqual(self._totales(self.aceite, [('date', '<=', '2031-03-31')])[0], 5.0)
        self.assertEqual(self._totales(self.aceite, [('date', '>=', '2031-04-01')])[0], 0.0)

    def test_sell_out_es_lo_facturado_menos_notas_de_credito(self):
        self._facturar(self.spray, 30, '2031-03-05')
        self._facturar(self.spray, 4, '2031-03-25', refund=True)
        self.assertEqual(self._totales(self.spray)[:2], (0.0, 26.0))
        self.assertAlmostEqual(self._totales(self.spray)[3], 10.4, places=3)

        factura = self.Sell.search([('product_id', '=', self.spray.id), ('cantidad', '>', 0)])
        self.assertEqual(factura.tipo, 'sell_out')
        self.assertEqual(factura.partner_id, self.cliente)
        self.assertEqual(str(factura.date), '2031-03-05')

    def test_sell_out_solo_facturas_publicadas_y_con_orden_de_venta(self):
        self._facturar(self.aceite, 7, '2031-03-05', publicar=False)
        self._facturar(self.aceite, 9, '2031-03-05', con_ov=False)
        self.assertEqual(self._totales(self.aceite)[1], 0.0)

    def test_sell_out_convierte_la_unidad_de_medida(self):
        self._facturar(self.aceite, 1, '2031-03-05', uom=self.docena)
        self.assertEqual(self._totales(self.aceite)[1], 12.0)

    def test_producto_sin_pilar_no_entra(self):
        self._recibir(self.sin_pilar, 10, '2031-03-10')
        self._facturar(self.sin_pilar, 3, '2031-03-12')
        self.assertEqual(self._totales(self.sin_pilar), (0.0, 0.0, 0.0, 0.0))

    def test_agrupa_por_mes_y_pilar(self):
        self._recibir(self.aceite, 10, '2031-03-10')
        self._recibir(self.aceite, 20, '2031-04-10')
        self._facturar(self.spray, 5, '2031-04-15')
        self.env.flush_all()
        grupos = self.Sell._read_group(
            [('product_id', 'in', (self.aceite + self.spray).ids)],
            ['date:month', 'pilar_id'], ['qty_in:sum', 'qty_out:sum'])
        resultado = {(mes.strftime('%Y-%m'), pilar): (qty_in, qty_out) for mes, pilar, qty_in, qty_out in grupos}
        self.assertEqual(resultado, {
            ('2031-03', self.pilar): (10.0, 0.0),
            ('2031-04', self.pilar): (20.0, 0.0),
            ('2031-04', self.pilar_b): (0.0, 5.0),
        })

    def test_regla_multi_compania(self):
        otro = self._producto('Aceite otra cía', 'COM-SELL-4', self.pilar, volumen=self.vol_5,
                              company=self.other_company)
        self._recibir(self.aceite, 10, '2031-03-10')
        self._recibir(otro, 6, '2031-03-10', company=self.other_company)
        self.env.flush_all()
        usuario = new_test_user(
            self.env, login='comercial_una_cia',
            groups='base.group_user,sng_comercial.group_sng_comercial_user',
            company_id=self.company.id, company_ids=[(6, 0, self.company.ids)])
        productos = (self.aceite + otro).ids
        visibles = self.Sell.with_user(usuario).search([('product_id', 'in', productos)])
        self.assertEqual(visibles.product_id, self.aceite)
        # El usuario de la prueba tiene las dos compañías.
        todos = self.Sell.search([('product_id', 'in', productos)])
        self.assertEqual(todos.product_id, self.aceite + otro)
        solo_una = self.Sell.with_context(allowed_company_ids=self.other_company.ids).search(
            [('product_id', 'in', productos)])
        self.assertEqual(solo_una.product_id, otro)
