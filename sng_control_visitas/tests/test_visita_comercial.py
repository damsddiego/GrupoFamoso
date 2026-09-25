# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.tests import tagged

from .common import ControlVisitasCommon


@tagged('post_install', '-at_install', 'sng_control_visitas')
class TestVisitaComercial(ControlVisitasCommon):

    def test_payload_viejo_sin_venta(self):
        """El payload actual de la app sigue funcionando y queda 'sin venta'."""
        v = self._visita(sng_uuid='uuid-1', lat=9.9, lng=-84.1)
        self.assertEqual(v.resultado_comercial, 'sin_venta')
        self.assertEqual(v.efectividad, 0.0)
        self.assertTrue(v.sin_comentario)
        self.assertFalse(v.requiere_seguimiento_televentas)

    def test_venta_pedido_pendiente_y_facturada(self):
        producto = self.env['product.product'].create({
            'name': 'Prod', 'list_price': 100.0, 'type': 'consu',
            'invoice_policy': 'order'})
        so = self.env['sale.order'].create({
            'partner_id': self.cliente.id,
            'order_line': [(0, 0, {'product_id': producto.id,
                                   'product_uom_qty': 2})],
        })
        so.action_confirm()
        v = self._visita(resultado='venta', sale_order_id=so.id)
        self.assertEqual(v.resultado_comercial, 'pedido_pendiente')
        self.assertEqual(v.efectividad, 0.5)
        self.assertAlmostEqual(v.monto_venta, so.amount_total)
        so._create_invoices().action_post()
        self.assertEqual(so.invoice_status, 'invoiced')
        self.assertEqual(v.resultado_comercial, 'venta_facturada')
        self.assertEqual(v.efectividad, 1.0)

    def test_valor_explicito_no_se_pisa(self):
        v = self._visita(resultado='venta',
                         resultado_comercial='cotizacion_enviada',
                         monto_venta=5000)
        self.assertEqual(v.resultado_comercial, 'cotizacion_enviada')
        self.assertEqual(v.monto_venta, 5000)

    def test_transferir_natalia_crea_pendiente(self):
        v = self._visita(proxima_accion_id=self.accion_transferir.id,
                         fecha_proxima_accion=date.today() + timedelta(days=3))
        self.assertTrue(v.requiere_seguimiento_televentas)
        self.assertEqual(len(v.seguimiento_ids), 1)
        seg = v.seguimiento_ids
        self.assertEqual(seg.estado, 'pendiente')
        self.assertEqual(seg.origen, 'solicitud_agente')
        self.assertEqual(seg.responsable_id, self.natalia)
        self.assertEqual(seg.semana.weekday(), 0)
        self.assertGreater(seg.semana, date.today() - timedelta(days=7))
        self.assertEqual(len(seg.activity_ids), 1)
        self.assertEqual(seg.activity_ids.user_id, self.natalia)

    def test_codigo_de_catalogo_desde_app(self):
        v = self._visita(proxima_accion_codigo='transferir_natalia',
                         motivo_sin_venta_codigo='otro',
                         comentario_tipo_codigo='agente_01')
        self.assertEqual(v.proxima_accion_id, self.accion_transferir)
        self.assertEqual(v.motivo_sin_venta_id, self.motivo_otro)
        self.assertTrue(v.comentario_tipo_id)
        self.assertFalse(v.sin_comentario)

    def test_reintento_uuid_no_duplica(self):
        v1 = self._visita(sng_uuid='uuid-rep',
                          proxima_accion_id=self.accion_transferir.id)
        v2 = self._visita(sng_uuid='uuid-rep',
                          proxima_accion_id=self.accion_transferir.id)
        self.assertEqual(v1, v2)
        self.assertEqual(self.Seg.search_count(
            [('partner_id', '=', self.cliente.id)]), 1)

    def test_no_visitado_pide_televentas(self):
        v = self._visita(resultado_comercial='no_visitado')
        self.assertTrue(v.requiere_seguimiento_televentas)
        self.assertFalse(v._es_visita_real())
        self.assertEqual(v.seguimiento_ids.origen, 'solicitud_agente')
        self.assertFalse(self.cliente.sng_fecha_ultima_visita)

    def test_nueva_visita_cierra_accion_anterior(self):
        v1 = self._visita(dias_atras=10,
                          proxima_accion_id=self.accion_cotizar.id,
                          fecha_proxima_accion=date.today() - timedelta(days=5))
        self.assertFalse(v1.accion_cerrada)
        self._visita(dias_atras=0)
        self.assertTrue(v1.accion_cerrada)

    def test_cerrar_seguimiento_marca_accion_cerrada(self):
        v = self._visita(proxima_accion_id=self.accion_cotizar.id,
                         fecha_proxima_accion=date.today())
        v.write({'proxima_accion_id': self.accion_cerrar.id})
        self.assertTrue(v.accion_cerrada)

    def test_fechas_partner(self):
        self._visita(dias_atras=3)
        self.assertEqual(self.cliente.sng_fecha_ultima_visita,
                         date.today() - timedelta(days=3))
        self.assertEqual(self.cliente.sng_fecha_proxima_visita,
                         date.today() + timedelta(days=27))
        self.cliente.sng_frecuencia_visita = 'bimensual'
        self.assertEqual(self.cliente.sng_fecha_proxima_visita,
                         date.today() + timedelta(days=57))
