# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'sng_cxc_report')
class TestCxcSnapshot(TransactionCase):
    """Snapshot CxC en una base multi-compañía con vendedor por compañía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context, tracking_disable=True, no_reset_password=True))
        cls.company = cls.env.company
        # Sin facturación electrónica ni candado de impuestos en pruebas.
        if 'frm_ws_ambiente' in cls.company._fields:
            cls.company.frm_ws_ambiente = 'disabled'
        Account = cls.env['account.account'].with_company(cls.company)
        cls.receivable = Account.search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', cls.company.id)], limit=1)
        cls.income = Account.search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', cls.company.id)], limit=1)

        cls.vendedor = cls.env['res.partner'].create({
            'name': 'Vendedor CxC Test', 'is_salesperson': True})
        cls.cliente = cls.env['res.partner'].create({
            'name': 'Cliente CxC Test', 'commercial_name': 'TIENDA CXC',
            'customer_rank': 1, 'company_id': cls.company.id})
        cls.cliente.with_company(cls.company).write({
            'assigned_salesperson_id': cls.vendedor.id,
            'property_account_receivable_id': cls.receivable.id,
        })
        cls.producto = cls.env['product.product'].create({
            'name': 'Producto CxC', 'type': 'consu', 'list_price': 100.0})
        cls.producto.with_company(cls.company).property_account_income_id = cls.income

        cls.hoy = fields.Date.context_today(cls.env['sng.cxc.report'])
        cls.factura = cls._factura(cls.hoy - timedelta(days=40), 100.0)

    @classmethod
    def _factura(cls, fecha, monto):
        inv = cls.env['account.move'].with_company(cls.company).create({
            'move_type': 'out_invoice',
            'partner_id': cls.cliente.id,
            'invoice_date': fecha,
            'invoice_date_due': fecha,
            'invoice_line_ids': [(0, 0, {
                'product_id': cls.producto.id,
                'quantity': 1,
                'price_unit': monto,
                'tax_ids': [(6, 0, [])],
            })],
        })
        inv.action_post()
        return inv

    def _snapshot(self):
        Report = self.env['sng.cxc.report'].with_context(
            allowed_company_ids=[self.company.id])
        Report._rebuild_snapshot(self.hoy)
        return Report.search([
            ('cutoff_date', '=', self.hoy),
            ('partner_id', '=', self.cliente.id),
            ('company_id', '=', self.company.id)])

    def test_snapshot_vendedor_por_compania_y_aging(self):
        fila = self._snapshot()
        self.assertEqual(len(fila), 1)
        self.assertEqual(fila.assigned_salesperson_id, self.vendedor)
        self.assertAlmostEqual(fila.total_receivable, 100.0, places=2)
        self.assertAlmostEqual(fila.positive_overdue_amount, 100.0, places=2)
        self.assertAlmostEqual(fila.bucket_31_45, 100.0, places=2)
        self.assertEqual(fila.dominant_bucket, 'bucket_31_45')
        self.assertEqual(fila.last_sale_date, self.hoy - timedelta(days=40))
        self.assertTrue(fila.action_plan_id)
        self.assertEqual(fila.action_plan_id.assigned_salesperson_id,
                         self.vendedor)
        linea = self.env['sng.cxc.report.line'].search([
            ('cutoff_date', '=', self.hoy),
            ('partner_id', '=', self.cliente.id),
            ('company_id', '=', self.company.id)])
        self.assertEqual(len(linea), 1)
        self.assertEqual(linea.move_id, self.factura)
        self.assertEqual(linea.assigned_salesperson_id, self.vendedor)
        self.assertEqual(linea.aging_bucket, 'bucket_31_45')

    def test_regenerar_es_idempotente(self):
        fila1 = self._snapshot()
        plan1 = fila1.action_plan_id
        plan1.write({'state': 'contacted', 'comments': 'llamado'})
        fila2 = self._snapshot()
        self.assertEqual(len(fila2), 1)
        # el plan de acción se conserva (misma identidad corte/compañía/cliente)
        self.assertEqual(fila2.action_plan_id, plan1)
        self.assertEqual(plan1.state, 'contacted')

    def test_bloqueo_credito_desde_plan(self):
        fila = self._snapshot()
        plan = fila.action_plan_id
        plan.action_block_credit()
        self.assertTrue(self.cliente.sng_credit_blocked)
        self.assertEqual(plan.state, 'blocked')
        with self.assertRaises(UserError):
            self._factura(self.hoy, 10.0)
        plan.action_unblock_credit()
        self.assertFalse(self.cliente.sng_credit_blocked)
        self.assertEqual(plan.state, 'pending')
