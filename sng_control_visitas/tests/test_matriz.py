# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ControlVisitasCommon


@tagged('post_install', '-at_install', 'sng_control_visitas')
class TestMatriz(ControlVisitasCommon):

    def _factura(self, partner, fecha):
        producto = self.env['product.product'].create({
            'name': 'Prod F', 'list_price': 10.0, 'type': 'consu'})
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fecha,
            'invoice_line_ids': [(0, 0, {'product_id': producto.id,
                                         'quantity': 1, 'price_unit': 10})],
        })
        inv.action_post()
        return inv

    def test_nunca_visitado_es_pendiente_y_desatendido(self):
        linea = self._linea(self.cliente)
        # nunca visitado en ruta con frecuencia: se espera visita este mes
        self.assertEqual(linea.estado_atencion, 'pendiente_visita')
        self.assertTrue(linea.cliente_desatendido)
        self.assertEqual(linea.responsable_proximo_paso, 'ambos')
        self.assertEqual(linea.alerta_gerencial, 'sin_atencion')
        self.assertEqual(linea.es_pendiente_compartido, 1)
        self.assertTrue(linea.nunca_facturo)
        self.assertEqual(linea.vendedor_id, self.agente)
        self.assertEqual(linea.sales_route_id, self.ruta)
        # nunca visitado: la visita se espera desde el inicio del período
        self.assertEqual(linea.fecha_visita_programada, linea.fecha_desde)

    def test_visitado_con_venta(self):
        v = self._visita(resultado_comercial='venta_facturada',
                         monto_venta=2500,
                         comentario_tipo_id=self.com_agente.id)
        linea = self._linea(self.cliente)
        self.assertEqual(linea.estado_atencion, 'visitado')
        self.assertEqual(linea.visita_id, v)
        self.assertEqual(linea.fecha_visita_realizada, date.today())
        self.assertEqual(linea.efectividad_visita, 1.0)
        self.assertEqual(linea.monto_venta_visita, 2500)
        self.assertFalse(linea.cliente_desatendido)
        self.assertEqual(linea.alerta_gerencial, 'ok')
        self.assertEqual(linea.es_venta_facturada, 1)
        self.assertEqual(linea.registros_sin_comentario, 0)

    def test_visita_sin_comentario_cuenta(self):
        self._visita(resultado_comercial='sin_venta')
        linea = self._linea(self.cliente)
        self.assertEqual(linea.registros_sin_comentario, 1)

    def test_solo_televentas(self):
        seg = self._seguimiento()
        seg.write({'canal': 'llamada', 'resultado': 'cotizacion_enviada',
                   'comentario': 'ok', 'estado': 'realizado',
                   'fecha_seguimiento': date.today()})
        linea = self._linea(self.cliente)
        self.assertEqual(linea.estado_atencion, 'solo_televentas')
        self.assertEqual(linea.efectividad_televentas, 0.5)
        self.assertEqual(linea.seguimiento_id, seg)
        self.assertFalse(linea.cliente_desatendido)
        self.assertEqual(linea.es_contacto_televentas, 1)

    def test_pendiente_visita_programada_sin_realizar(self):
        self._visita(dias_atras=40)  # visita real hace 40 días
        # próxima esperada = hace 10 días → programada dentro del mes si cae
        hoy = date.today()
        linea = self._linea(self.cliente)
        proxima = self.cliente.sng_fecha_proxima_visita
        if linea.fecha_desde <= proxima <= linea.fecha_hasta:
            self.assertEqual(linea.estado_atencion, 'pendiente_visita')
            self.assertTrue(linea.cliente_desatendido)
        else:
            # la visita esperada cayó en el mes anterior: sin gestión este mes
            self.assertIn(linea.estado_atencion, ('pendiente_visita', 'sin_gestion'))
        self.assertEqual(linea.alerta_gerencial, 'sin_atencion')
        self.assertLess(proxima, hoy)

    def test_seguimiento_vencido_agente(self):
        self._visita(resultado_comercial='sin_venta',
                     comentario_agente='sin stock',
                     proxima_accion_id=self.accion_cotizar.id,
                     fecha_proxima_accion=date.today() - timedelta(days=2))
        linea = self._linea(self.cliente)
        self.assertEqual(linea.responsable_proximo_paso, 'agente')
        self.assertEqual(linea.alerta_gerencial, 'seguimiento_vencido')
        self.assertEqual(linea.es_pendiente_agente, 1)
        self.assertEqual(linea.es_seguimiento_vencido, 1)

    def test_accion_hoy_no_vencida(self):
        self._visita(resultado_comercial='sin_venta',
                     comentario_agente='x',
                     proxima_accion_id=self.accion_cotizar.id,
                     fecha_proxima_accion=date.today())
        linea = self._linea(self.cliente)
        self.assertEqual(linea.responsable_proximo_paso, 'agente')
        self.assertEqual(linea.alerta_gerencial, 'ok')

    def test_mas_90_dias_sin_facturar(self):
        self._factura(self.cliente, date.today() - timedelta(days=120))
        self._visita(resultado_comercial='sin_venta', comentario_agente='x')
        linea = self._linea(self.cliente)
        self.assertEqual(linea.last_invoice_date,
                         date.today() - timedelta(days=120))
        self.assertEqual(linea.dias_sin_facturar, 120)
        self.assertEqual(linea.alerta_gerencial, 'mas_90_dias')
        self.assertEqual(linea.es_mas_90_dias, 1)

    def test_sin_visita_programada_es_sin_gestion(self):
        self.cliente.sng_frecuencia_visita = 'sin_visita'
        linea = self._linea(self.cliente)
        self.assertEqual(linea.estado_atencion, 'sin_gestion')
        self.assertFalse(linea.cliente_desatendido)
        self.assertEqual(linea.alerta_gerencial, 'ok')

    def test_bimensual_no_desatendido(self):
        self.cliente.sng_frecuencia_visita = 'bimensual'
        self._visita(dias_atras=20, resultado_comercial='sin_venta',
                     comentario_agente='x')
        mes_siguiente = (date.today().replace(day=28) + timedelta(days=5))
        # generar el mes siguiente: no hay visita, pero la próxima esperada
        # (hace 20 días + 60) cae después del cierre de ese mes o dentro
        linea = self._linea(self.cliente, mes_siguiente)
        proxima = self.cliente.sng_fecha_proxima_visita
        if proxima > linea.fecha_hasta:
            self.assertFalse(linea.cliente_desatendido)
            self.assertEqual(linea.estado_atencion, 'sin_gestion')
        else:
            self.assertTrue(linea.cliente_desatendido)

    def test_televentas_esperado_por_frecuencia(self):
        linea = self._linea(self.cliente_tv)
        self.assertEqual(linea.tipo_atencion, 'televentas')
        self.assertTrue(linea.cliente_desatendido)
        seg = self._seguimiento(partner=self.cliente_tv)
        seg.write({'canal': 'llamada', 'resultado': 'sin_interes',
                   'comentario': 'x', 'estado': 'realizado',
                   'fecha_seguimiento': date.today()})
        linea = self._linea(self.cliente_tv)
        self.assertFalse(linea.cliente_desatendido)
        self.assertEqual(linea.estado_atencion, 'solo_televentas')

    def test_kpis_y_regeneracion_idempotente(self):
        self._visita(resultado_comercial='venta_facturada', monto_venta=100,
                     comentario_agente='x')
        seg = self._seguimiento(partner=self.cliente2)
        seg.write({'canal': 'llamada', 'resultado': 'venta_recuperada',
                   'monto_venta': 50, 'comentario': 'x',
                   'estado': 'realizado', 'fecha_seguimiento': date.today()})
        hoy = fields.Date.context_today(self.Linea)
        self.Linea._sng_generar_mes(hoy, self.company)
        n1 = self.Linea.search_count([('periodo', '=', hoy.strftime('%Y-%m'))])
        self.Linea._sng_generar_mes(hoy, self.company)
        n2 = self.Linea.search_count([('periodo', '=', hoy.strftime('%Y-%m'))])
        self.assertEqual(n1, n2)
        k = self.Linea._sng_kpis(hoy.strftime('%Y-%m'), self.company)
        self.assertGreaterEqual(k['total_clientes'], 3)
        self.assertGreaterEqual(k['clientes_visitados'], 1)
        self.assertGreaterEqual(k['ventas_recuperadas'], 1)
        self.assertGreaterEqual(k['monto_ventas_visita'], 100)
        self.assertGreaterEqual(k['monto_ventas_televentas'], 50)
        self.assertGreater(k['pct_cobertura_visitas'], 0)
        self.assertLessEqual(k['pct_atencion_total'], 1)
        # sin datos: porcentajes en 0, no división por cero
        k0 = self.Linea._sng_kpis('1900-01', self.company)
        self.assertEqual(k0['pct_cobertura_visitas'], 0)
        self.assertEqual(k0['total_clientes'], 0)

    def test_credito_bloqueado_fuera_de_matriz(self):
        self.assertTrue(self._linea(self.cliente2))
        self.cliente2.sng_credit_blocked = True
        # la regeneración borra la línea que ya existía para el período
        self.assertFalse(self._linea(self.cliente2))
        self.assertTrue(self._linea(self.cliente))

    def test_excluido_y_compania_fuera_de_matriz(self):
        self.cliente2.sng_excluir_matriz = True
        self.assertFalse(self._linea(self.cliente2))
        self.assertFalse(self._linea(self.company.partner_id))
        self.assertTrue(self._linea(self.cliente))

    def test_marcar_clientes_genericos(self):
        from ..hooks import marcar_clientes_genericos
        Partner = self.env['res.partner']
        tiquete = Partner.create({
            'name': 'OCASIONAL AGENTE MAYORISTA TIQUETE', 'customer_rank': 1})
        publico = Partner.create({
            'name': 'Cliente ocacional Publico', 'customer_rank': 1})
        # "ocasional" en medio del nombre no es un cliente genérico
        normal = Partner.create({
            'name': 'Tienda La Ocasional', 'customer_rank': 1})
        marcar_clientes_genericos(self.env)
        self.assertTrue(tiquete.sng_excluir_matriz)
        self.assertTrue(publico.sng_excluir_matriz)
        self.assertFalse(normal.sng_excluir_matriz)
        self.assertFalse(self._linea(tiquete))

    def test_resumen_gerencial_publica(self):
        self.Linea._sng_cron_resumen_gerencial()
        channel = self.env.ref('sng_control_visitas.channel_control_visitas')
        msgs = channel.message_ids.filtered(
            lambda m: 'Control de visitas' in (m.body or ''))
        self.assertTrue(msgs)
