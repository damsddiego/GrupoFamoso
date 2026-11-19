# -*- coding: utf-8 -*-
"""Comprobaciones de la migración a cuadros (18.0.6.0.0) sobre datos reales.

Solo corren en una copia neutralizada de prod_gf y se saltan si no tiene el
cierre de octubre de 2026:

    --test-tags /sng_sales_commission_payment:TestMigracionCopiaProd
"""
from datetime import date

from odoo.tests import TransactionCase, tagged

OCTUBRE = date(2026, 10, 1)


@tagged('post_install', '-at_install', 'sng_copia_prod')
class TestMigracionCopiaProd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Monthly = cls.env['sng.commission.monthly']

    def setUp(self):
        super().setUp()
        if not self.Monthly.search_count([('period', '=', OCTUBRE), ('state', '!=', 'draft')]):
            self.skipTest('Sin el cierre de octubre 2026 de prod_gf en esta base.')

    def test_lo_anterior_al_cuadro_de_grupo_sigue_por_compania(self):
        """Antes del primer cuadro de varias compañías, cada mensual quedó en
        un cuadro de una sola compañía, la suya."""
        grupos = self.env['sng.commission.scheme'].with_context(active_test=False).search([]).filtered(
            lambda s: len(s.company_ids) > 1 and s.date_start)
        desde = min(grupos.mapped('date_start')) if grupos else OCTUBRE.replace(month=11)
        viejos = self.Monthly.search([('period', '<', desde)])
        self.assertTrue(viejos)
        for mensual in viejos:
            self.assertEqual(mensual.scheme_id.company_ids, mensual.company_id, mensual.name)

    def test_los_tramos_guardados_son_del_cuadro_del_mensual(self):
        for mensual in self.Monthly.search([('tier_id', '!=', False)]):
            self.assertEqual(mensual.tier_id.scheme_id, mensual.scheme_id, mensual.name)

    def test_sin_cuadro_de_grupo_no_hay_nada_que_reagrupar(self):
        grupos = self.env['sng.commission.scheme'].search([]).filtered(lambda s: len(s.company_ids) > 1)
        if grupos:
            self.skipTest('La base ya tiene un cuadro de varias compañías.')
        res = self.Monthly._sng_regroup_open(dry_run=True)
        self.assertEqual((res['moved_lines'], res['removed_monthlies'], res['skipped']), (0, 0, []))

    def test_usuario_sin_grupo_genera_lineas(self):
        """Confirmar un cobro lo hace cualquier usuario de facturación, sin
        permisos sobre comisiones ni sobre los cuadros."""
        Line = self.env['sng.commission.payment.line']
        linea = Line.search([
            ('line_type', '=', 'commission'), ('monthly_id.state', '=', 'draft'),
            ('payment_id.state', 'in', ('in_process', 'paid')),
        ], order='id desc', limit=1)
        if not linea:
            self.skipTest('Sin líneas de comisión en un mes pendiente.')
        pago = linea.payment_id
        usuario = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario de facturación sin comisiones',
            'login': 'prueba_facturacion_sin_comisiones',
            'company_id': pago.company_id.id,
            'company_ids': [(6, 0, pago.company_id.ids)],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_invoice').id,
            ])],
        })
        antes = Line.search([('payment_id', '=', pago.id)])
        base = sum(antes.mapped('commission_base'))
        pago.with_user(usuario).with_company(pago.company_id)._generate_commission_lines()
        despues = Line.search([('payment_id', '=', pago.id)])
        self.assertEqual(despues, antes)
        self.assertAlmostEqual(sum(despues.mapped('commission_base')), base, places=2)


@tagged('post_install', '-at_install', 'sng_copia_prod')
class TestGrupoCopiaProd(TransactionCase):
    """Cobros y desconciliaciones reales contra un cuadro de varias compañías.

    Solo corren en una copia neutralizada de prod_gf que ya tenga un cuadro de
    grupo vigente (después de la puesta en marcha); si no, se saltan.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Monthly = cls.env['sng.commission.monthly']
        cls.Line = cls.env['sng.commission.payment.line']
        cls.hoy = cls.env['account.payment']._sng_confirmation_today()
        cls.periodo = cls.hoy.replace(day=1)

    def setUp(self):
        super().setUp()
        self.grupo = self.env['sng.commission.scheme'].search([]).filtered(
            lambda s: len(s.company_ids) > 1 and (not s.date_start or s.date_start <= self.periodo))[:1]
        if not self.grupo:
            self.skipTest('La base no tiene un cuadro de varias compañías vigente.')

    def _usuario_de_facturacion(self, company):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario de facturación sin comisiones',
            'login': 'prueba_facturacion_grupo',
            'company_id': company.id,
            'company_ids': [(6, 0, company.ids)],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_invoice').id,
            ])],
        })

    def test_cobro_real_entra_al_mensual_del_grupo(self):
        """Un cobro del mes, ya aplicado y todavía sin línea, lo genera un
        usuario de facturación de una sola compañía y cae en el mensual único
        del vendedor."""
        desde, hasta = self.Monthly._sng_period_bounds(self.periodo)
        par = None
        for company in self.grupo.company_ids:
            if self.env['sng.commission.scheme']._get_for_company(company, self.periodo) != self.grupo:
                continue
            par = next((r for r in self.Monthly._sng_find_uncommissioned(company, desde, hasta)
                        if r['salesperson_id']), None)
            if par:
                break
        if not par:
            self.skipTest('Sin cobros del mes pendientes de comisión.')
        pago = self.env['account.payment'].browse(par['payment_id'])
        mensual = self.Monthly.search([
            ('salesperson_id', '=', par['salesperson_id']), ('scheme_id', '=', self.grupo.id),
            ('period', '=', self.periodo)])
        base_antes, lineas_antes = mensual.base_amount, len(mensual.line_ids)
        usuario = self._usuario_de_facturacion(pago.company_id)
        pago.with_user(usuario).with_company(pago.company_id)._generate_commission_lines()

        nuevas = self.Line.search([('payment_id', '=', pago.id), ('line_type', '=', 'commission')])
        self.assertTrue(nuevas)
        del_vendedor = nuevas.filtered(lambda l: l.salesperson_id.id == par['salesperson_id'])
        self.assertTrue(del_vendedor)
        mensual = del_vendedor.monthly_id
        self.assertEqual(len(mensual), 1)
        self.assertEqual((mensual.scheme_id, mensual.period, mensual.state), (self.grupo, self.periodo, 'draft'))
        self.assertEqual(len(mensual.line_ids), lineas_antes + len(del_vendedor))
        self.assertAlmostEqual(
            mensual.base_amount, base_antes + sum(del_vendedor.mapped('commission_base')), places=2)

    def test_desconciliar_un_cobro_de_un_mes_cerrado_resta_en_el_grupo(self):
        """Romper la aplicación de un cobro de un mes cerrado (por compañía)
        deja ese mes intacto y descuenta lo pagado en el mensual del grupo."""
        candidatas = self.Line.search([
            ('line_type', '=', 'commission'), ('monthly_id.state', '=', 'closed'),
            ('monthly_id.percentage', '>', 0), ('reversal_line_ids', '=', False),
            ('company_id', 'in', self.grupo.company_ids.ids),
            ('payment_id.state', 'in', ('in_process', 'paid')),
        ], order='id desc', limit=40)
        linea = parcial = None
        for candidata in candidatas:
            for factura, partial, _monto in candidata.payment_id._get_reconciled_invoice_partials():
                if factura == candidata.invoice_id:
                    linea, parcial = candidata, partial
                    break
            if linea:
                break
        if not linea:
            self.skipTest('Sin un cobro de un mes cerrado que siga aplicado a su factura.')
        original = linea.monthly_id
        foto = (original.base_amount, original.percentage, original.commission_amount, original.state)
        pagado = linea.commission_base * original.percentage / 100.0

        parcial.unlink()

        reverso = linea.reversal_line_ids
        self.assertEqual(len(reverso), 1)
        self.assertEqual(reverso.monthly_id.scheme_id, self.grupo)
        self.assertEqual(reverso.monthly_id.state, 'draft')
        self.assertGreaterEqual(reverso.monthly_id.period, self.periodo)
        self.assertAlmostEqual(reverso.commission_adjustment, -pagado, places=2)
        self.assertEqual(reverso.monthly_id.salesperson_id, linea.salesperson_id)
        self.assertEqual(
            (original.base_amount, original.percentage, original.commission_amount, original.state), foto)
        self.assertTrue(linea.exists())
