# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ControlVisitasCommon


@tagged('post_install', '-at_install', 'sng_control_visitas')
class TestSeguimiento(ControlVisitasCommon):

    def test_pendiente_crea_actividad(self):
        seg = self._seguimiento(semana=date(2026, 9, 9))  # miércoles
        self.assertEqual(seg.semana, date(2026, 9, 7))
        self.assertEqual(seg.fecha_limite, date(2026, 9, 13))
        self.assertEqual(seg.responsable_id, self.natalia)
        self.assertEqual(len(seg.activity_ids), 1)
        act = seg.activity_ids
        self.assertEqual(act.user_id, self.natalia)
        self.assertEqual(act.date_deadline, date(2026, 9, 13))
        seg.fecha_proxima_accion = date(2026, 9, 10)
        self.assertEqual(seg.activity_ids.date_deadline, date(2026, 9, 10))

    def test_realizado_exige_comentario(self):
        seg = self._seguimiento()
        with self.assertRaises(ValidationError):
            seg.write({'estado': 'realizado', 'canal': 'llamada',
                       'resultado': 'sin_interes',
                       'fecha_seguimiento': date.today()})

    def test_realizado_cierra_actividad_y_visita(self):
        v = self._visita(proxima_accion_id=self.accion_transferir.id,
                         fecha_proxima_accion=date.today())
        seg = v.seguimiento_ids
        seg.write({'canal': 'whatsapp', 'resultado': 'venta_recuperada',
                   'monto_venta': 1200, 'comentario_tipo_id': self.com_tv.id})
        seg.action_marcar_realizado()
        self.assertEqual(seg.estado, 'realizado')
        self.assertEqual(seg.fecha_seguimiento, date.today())
        self.assertEqual(seg.efectividad, 1.0)
        self.assertFalse(seg.activity_ids)
        self.assertTrue(v.accion_cerrada)
        self.assertEqual(self.cliente.sng_fecha_ultimo_contacto_televentas,
                         date.today())

    def test_reprogramar_crea_nuevo_pendiente(self):
        seg = self._seguimiento()
        seg.write({'canal': 'llamada', 'resultado': 'reprogramar_llamada',
                   'comentario': 'Llamar el lunes',
                   'fecha_proxima_accion': date.today() + timedelta(days=8)})
        seg.action_marcar_realizado()
        nuevo = self.Seg.search([('partner_id', '=', self.cliente.id),
                                 ('estado', '=', 'pendiente')])
        self.assertEqual(len(nuevo), 1)
        self.assertEqual(nuevo.fecha_proxima_accion,
                         date.today() + timedelta(days=8))
        self.assertEqual(nuevo.activity_ids.date_deadline,
                         date.today() + timedelta(days=8))

    def test_unico_pendiente_por_semana(self):
        self._seguimiento(semana=date.today())
        with self.assertRaises(ValidationError):
            self._seguimiento(semana=date.today())

    def test_vencido(self):
        seg = self._seguimiento(semana=date.today() - timedelta(days=14))
        self.assertTrue(seg.vencido)
        self.assertIn(seg, self.Seg.search([('vencido', '=', True)]))
        seg.action_cancelar()
        self.assertFalse(seg.vencido)
        self.assertFalse(seg.activity_ids)
