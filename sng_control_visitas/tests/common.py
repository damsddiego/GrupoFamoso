# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, new_test_user


class ControlVisitasCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context, tracking_disable=True, no_reset_password=True))
        cls.company = cls.env.company
        cls.grupo_user = cls.env.ref(
            'sng_control_visitas.group_control_visitas_user')
        cls.natalia = new_test_user(
            cls.env, login='natalia_test',
            groups='base.group_user,sng_control_visitas.group_control_visitas_user,'
                   'sales_team.group_sale_salesman')
        cls.company.sng_televentas_user_id = cls.natalia
        cls.company.sng_control_visitas_dias_alerta_factura = 90
        # Las pruebas no validan facturación electrónica de Costa Rica.
        if 'frm_ws_ambiente' in cls.company._fields:
            cls.company.frm_ws_ambiente = 'disabled'
        if 'invoice_is_electronic' in cls.company._fields:
            cls.company.invoice_is_electronic = False

        cls.agente = cls.env['res.partner'].create({
            'name': 'Agente Prueba', 'is_salesperson': True})
        cls.ruta = cls.env['sng.sales.route'].create({
            'name': 'RUTA TEST', 'code': 'TEST',
            'salesperson_id': cls.agente.id,
            'sng_tipo_atencion': 'ruta',
            'sng_frecuencia_visita': 'mensual',
        })
        cls.ruta_tv = cls.env['sng.sales.route'].create({
            'name': 'TELEVENTAS TEST', 'code': 'TVTEST',
            'sng_tipo_atencion': 'televentas',
            'sng_frecuencia_visita': 'mensual',
        })
        cls.cliente = cls.env['res.partner'].create({
            'name': 'Cliente Uno', 'commercial_name': 'TIENDA UNO',
            'customer_rank': 1, 'sales_route_id': cls.ruta.id,
            'assigned_salesperson_id': cls.agente.id,
            'company_id': cls.company.id,
        })
        cls.cliente2 = cls.env['res.partner'].create({
            'name': 'Cliente Dos', 'commercial_name': 'TIENDA DOS',
            'customer_rank': 1, 'sales_route_id': cls.ruta.id,
            'assigned_salesperson_id': cls.agente.id,
            'company_id': cls.company.id,
        })
        cls.cliente_tv = cls.env['res.partner'].create({
            'name': 'Cliente Tele', 'commercial_name': 'TIENDA TELE',
            'customer_rank': 1, 'sales_route_id': cls.ruta_tv.id,
            'company_id': cls.company.id,
        })
        Cat = cls.env['sng.visita.catalogo']
        cls.accion_transferir = Cat._sng_buscar_codigo(
            'proxima_accion', 'transferir_natalia')
        cls.accion_cerrar = Cat._sng_buscar_codigo(
            'proxima_accion', 'cerrar_seguimiento')
        cls.accion_cotizar = Cat._sng_buscar_codigo(
            'proxima_accion', 'enviar_cotizacion')
        cls.motivo_otro = Cat._sng_buscar_codigo('motivo_sin_venta', 'otro')
        cls.com_agente = Cat.search(
            [('tipo', '=', 'comentario_agente')], limit=1)
        cls.com_tv = Cat.search(
            [('tipo', '=', 'comentario_televentas')], limit=1)
        cls.Visita = cls.env['sng.ruteros.visita']
        cls.Seg = cls.env['sng.televentas.seguimiento']
        cls.Linea = cls.env['sng.control.visitas.linea']

    def _visita(self, partner=None, dias_atras=0, **vals):
        fecha = datetime.now() - timedelta(days=dias_atras)
        base = {
            'partner_id': (partner or self.cliente).id,
            'vendedor_id': self.agente.id,
            'company_id': self.company.id,
            'fecha_inicio': fecha,
            'resultado': 'visita',
        }
        base.update(vals)
        return self.Visita.create(base)

    def _seguimiento(self, partner=None, **vals):
        base = {
            'partner_id': (partner or self.cliente).id,
            'company_id': self.company.id,
            'origen': 'manual',
        }
        base.update(vals)
        return self.Seg.create(base)

    def _linea(self, partner, fecha=None):
        from odoo import fields
        fecha = fecha or fields.Date.context_today(self.Linea)
        self.Linea._sng_generar_mes(fecha, self.company)
        return self.Linea.search([
            ('partner_id', '=', partner.id),
            ('periodo', '=', fecha.strftime('%Y-%m')),
            ('company_id', '=', self.company.id)])
