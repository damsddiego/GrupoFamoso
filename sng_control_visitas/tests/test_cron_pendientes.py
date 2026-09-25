# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo.tests import tagged

from .common import ControlVisitasCommon


@tagged('post_install', '-at_install', 'sng_control_visitas')
class TestCronPendientes(ControlVisitasCommon):

    def setUp(self):
        super().setUp()
        hoy = date.today()
        # misma regla que el cron: en domingo la semana es la que empieza
        self.semana = self.Seg._sng_lunes(hoy + timedelta(days=1))
        self.prev = self.semana - timedelta(days=7)
        # mitad de la semana previa, a mediodía
        self.dt_prev = datetime.combine(
            self.prev + timedelta(days=2), datetime.min.time()
        ).replace(hour=15)

    def _pendientes(self, partner):
        return self.Seg.search([('partner_id', '=', partner.id),
                                ('estado', '=', 'pendiente')])

    def test_no_visitado_semana_previa(self):
        self._visita(fecha_inicio=self.dt_prev,
                     resultado_comercial='no_visitado')
        # la visita ya creó su pendiente al registrarse (requiere televentas)
        self.assertEqual(len(self._pendientes(self.cliente)), 1)
        self.Linea._sng_cron_generar_pendientes()
        self.assertEqual(len(self._pendientes(self.cliente)), 1)

    def test_visita_no_real_sin_flag_genera_no_visitado(self):
        v = self._visita(fecha_inicio=self.dt_prev,
                         resultado_comercial='visita_reprogramada')
        v.seguimiento_ids.unlink()
        v.requiere_seguimiento_televentas = False
        self.Linea._sng_cron_generar_pendientes()
        seg = self._pendientes(self.cliente)
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg.origen, 'no_visitado')
        self.assertEqual(seg.visita_id, v)
        self.assertEqual(seg.semana, self.semana)

    def test_visita_pendiente_por_frecuencia(self):
        # visitado hace 45 días con frecuencia mensual → vencido
        self._visita(dias_atras=45, resultado_comercial='sin_venta',
                     comentario_agente='x')
        self.Linea._sng_cron_generar_pendientes()
        seg = self._pendientes(self.cliente)
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg.origen, 'visita_pendiente')

    def test_visitado_semana_previa_no_genera(self):
        self._visita(fecha_inicio=self.dt_prev,
                     resultado_comercial='sin_venta', comentario_agente='x')
        self.Linea._sng_cron_generar_pendientes()
        self.assertFalse(self._pendientes(self.cliente))

    def test_frecuencia_televentas(self):
        self.Linea._sng_cron_generar_pendientes()
        seg = self._pendientes(self.cliente_tv)
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg.origen, 'frecuencia_televentas')

    def test_excluye_pendiente_abierto_y_es_idempotente(self):
        self._seguimiento(partner=self.cliente_tv,
                          semana=self.semana - timedelta(days=7))
        self.Linea._sng_cron_generar_pendientes()
        self.assertEqual(len(self._pendientes(self.cliente_tv)), 1)
        self.Linea._sng_cron_generar_pendientes()
        self.assertEqual(len(self._pendientes(self.cliente_tv)), 1)

    def test_nunca_visitado_sin_factura_no_genera(self):
        # cliente nuevo sin facturas ni visitas: no se molesta a televentas
        self.Linea._sng_cron_generar_pendientes()
        self.assertFalse(self._pendientes(self.cliente2))
