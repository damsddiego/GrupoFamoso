# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged

from .common import ComisionGrupoCase


@tagged('post_install', '-at_install')
class TestUsuarioUnaCompania(ComisionGrupoCase):
    """Un usuario de comisiones que solo tiene activa una de las compañías del
    cuadro ve y calcula la comisión completa: el mensual es uno solo."""

    def setUp(self):
        super().setUp()
        self.grupo = self._cuadro('Grupo', self.cia_a | self.cia_b, date(2031, 3, 1))
        self.m = self.Monthly._get_or_create(self.vendedor, self.cia_a, date(2031, 3, 1))
        self._linea(self.m, self.cia_a, 26076324.10)
        self._linea(self.m, self.cia_b, 3068166.99)
        self.m._recompute_commission()
        self.admin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Administrador de comisiones de una compañía',
            'login': 'prueba_admin_comisiones_una_cia',
            'company_id': self.cia_a.id,
            'company_ids': [(6, 0, self.cia_a.ids)],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_commission_omax.group_sales_commission_manager').id,
            ])],
        })
        self.env.flush_all()
        self.env.invalidate_all()

    def _como_admin(self, registro):
        return registro.with_user(self.admin).with_context(allowed_company_ids=self.cia_a.ids)

    def test_recalcular_usa_todas_las_lineas(self):
        self._como_admin(self.m)._recompute_commission()
        self.assertAlmostEqual(self.m.base_amount, 29144491.09, places=2)
        self.assertEqual(self.m.percentage, 3.5)

    def test_reabrir_no_pierde_la_base_de_las_otras_companias(self):
        self.m.write({'closed': True})
        self.env.flush_all()
        self.env.invalidate_all()
        self._como_admin(self.m).action_reopen()
        self.assertEqual(self.m.state, 'draft')
        self.assertAlmostEqual(self.m.base_amount, 29144491.09, places=2)
        self.assertAlmostEqual(self.m.commission_amount, 1020057.19, places=2)

    def test_cerrar_no_pierde_la_base_de_las_otras_companias(self):
        self._como_admin(self.m).action_close()
        self.assertEqual(self.m.state, 'closed')
        self.assertAlmostEqual(self.m.base_amount, 29144491.09, places=2)

    def test_abre_el_formulario_con_todas_sus_lineas(self):
        datos = self._como_admin(self.m).web_read({
            'scheme_id': {'fields': {'display_name': {}}},
            'company_names': {},
            'company_breakdown_html': {},
            'commission_line_ids': {'fields': {
                'invoice_id': {'fields': {'display_name': {}}},
                'payment_id': {'fields': {'display_name': {}}},
                'partner_id': {'fields': {'display_name': {}}},
                'commission_base': {},
            }},
        })[0]
        self.assertIn(self.cia_b.name, datos['company_names'])
        self.assertEqual(len(datos['commission_line_ids']), 2)
        self.assertAlmostEqual(sum(l['commission_base'] for l in datos['commission_line_ids']), 29144491.09, places=2)

    def test_lista_de_cuadros_y_asistentes_no_leen_companias_ajenas(self):
        cuadro = self._como_admin(self.grupo).web_read({'name': {}, 'company_names': {}})[0]
        self.assertIn(self.cia_b.name, cuadro['company_names'])
        for modelo in ('sng.close.commission.wiz', 'sng.commission.report.wiz'):
            asistente = self._como_admin(self.env[modelo]).create({'period': date(2031, 3, 15), 'scheme_id': self.grupo.id})
            datos = asistente.web_read({'company_names': {}, 'scheme_id': {'fields': {'display_name': {}}}})[0]
            self.assertIn(self.cia_b.name, datos['company_names'], modelo)
        vistas = [
            self.env['sng.commission.monthly'].get_view(view_type='form')['arch'],
            self.env['sng.commission.monthly'].get_view(view_type='list')['arch'],
            self.env['sng.commission.scheme'].get_view(view_type='list')['arch'],
            self.env['sng.close.commission.wiz'].get_view(view_type='form')['arch'],
            self.env['sng.commission.report.wiz'].get_view(view_type='form')['arch'],
        ]
        for arch in vistas:
            self.assertNotIn('name="company_ids"', arch)

    def test_cada_pantalla_abre_con_una_sola_compania_activa(self):
        """Como las abre el navegador: con todos los campos de la vista."""
        mensual = self._leer_como_cliente(self._como_admin(self.m))
        self.assertEqual(len(mensual['commission_line_ids']), 2)
        self._leer_como_cliente(self._como_admin(self.m), 'list')
        self._leer_como_cliente(self._como_admin(self.grupo), 'list')
        reporte = self._como_admin(self.env['sng.commission.report.wiz']).create({
            'period': date(2031, 3, 15), 'scheme_id': self.grupo.id})
        self.assertEqual(self._leer_como_cliente(reporte)['monthly_count'], 1)

    def test_cierre_abre_aunque_haya_facturas_sin_vendedor_de_otra_compania(self):
        factura_b = self.env['account.move'].search([
            ('company_id', '=', self.cia_b.id), ('move_type', '=', 'out_invoice'), ('state', '=', 'posted')], limit=1)
        if not factura_b:
            self.skipTest('Sin facturas en %s.' % self.cia_b.name)
        pendientes = {self.cia_b.id: [{'payment_id': 0, 'invoice_id': factura_b.id, 'salesperson_id': None}]}
        with patch.object(type(self.Monthly), '_sng_find_uncommissioned', autospec=True,
                          side_effect=lambda _self, company, _d, _h: pendientes.get(company.id, [])):
            cierre = self._como_admin(self.env['sng.close.commission.wiz']).create({
                'period': date(2031, 3, 15), 'scheme_id': self.grupo.id})
            datos = self._leer_como_cliente(cierre)
            self.assertEqual(datos['no_salesperson_invoice_count'], 1)
            self.assertEqual(datos['pending_count'], 1)
            accion = cierre.action_view_no_salesperson_invoices()
        self.assertEqual(accion['domain'], [('id', 'in', [factura_b.id])])

    def test_analisis_y_reportes_completos(self):
        m = self._como_admin(self.m)
        origen = m._sng_analysis_origin()
        self.assertAlmostEqual(origen['check']['base'], 29144491.09, places=2)
        self.assertAlmostEqual(origen['check']['difference'], 0.0, places=2)
        self.assertAlmostEqual(
            sum(fila['commission_base'] for fila in m._get_tax_profile_summary()), 29144491.09, places=2)
        m._sng_analysis_credit_notes()
        m._sng_analysis_prior_collections()
        m._sng_analysis_unreturned_reversals()
        html = self.env['ir.actions.report'].with_user(self.admin).with_context(
            allowed_company_ids=self.cia_a.ids)._render_qweb_html(
                'sng_sales_commission_payment.report_commission_monthly', self.m.ids)[0]
        html = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn('Por Compañía', html)
        self.assertIn(self.cia_b.name, html)
        self.env['ir.actions.report'].with_user(self.admin).with_context(
            allowed_company_ids=self.cia_a.ids)._render(
                'sng_sales_commission_payment.commission_monthly_xlsx', self.m.ids)
