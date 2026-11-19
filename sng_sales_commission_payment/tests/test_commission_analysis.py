# -*- coding: utf-8 -*-
"""Pruebas del análisis de la comisión (v18.0.5.5.0).

Dependen de los datos de octubre de 2026 de prod_gf, revisados contra SQL
independiente el 2026-11-13 (Eduardo Rodríguez y Jorge Luis Cubillo): solo
corren en una copia neutralizada de prod_gf posterior a esa fecha y se saltan
si esos datos no existen.

    --test-tags /sng_sales_commission_payment:TestCommissionAnalysis
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

OCTOBER = date(2026, 10, 1)
EDUARDO = 17
CUBILLO = 14811
CUBILLO_DUP = 14202
PROTIRE = 2
SAASA = 3


@tagged('post_install', '-at_install', 'sng_copia_prod')
class TestCommissionAnalysis(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Monthly = cls.env['sng.commission.monthly']

    def _monthly(self, salesperson_id, company_id):
        monthly = self.Monthly.search([
            ('salesperson_id', '=', salesperson_id),
            ('company_id', '=', company_id),
            ('period', '=', OCTOBER),
            ('state', '!=', 'draft'),
        ], limit=1)
        if not monthly:
            self.skipTest('Sin el cierre de octubre 2026 de prod_gf en esta base.')
        return monthly

    def test_origin_matches_module_for_every_monthly(self):
        """Los grupos de origen suman la base, cuentan cada pago una vez y el
        cuadre da el monto del módulo, en todos los mensuales cerrados (un mes
        abierto puede ir un céntimo atrás hasta su próximo recálculo)."""
        for monthly in self.Monthly.search([('state', '!=', 'draft')]):
            origin = monthly._sng_analysis_origin()
            base = sum(group['commission_base'] for group in origin['groups'])
            self.assertAlmostEqual(base, monthly.base_amount, places=2, msg=monthly.name)
            self.assertEqual(
                sum(group['payment_count'] for group in origin['groups']),
                len(monthly.commission_line_ids.mapped('payment_id')), monthly.name)
            self.assertAlmostEqual(origin['check']['difference'], 0.0, places=2, msg=monthly.name)

    def test_eduardo_protire_origin(self):
        monthly = self._monthly(EDUARDO, PROTIRE)
        origin = monthly._sng_analysis_origin()
        self.assertAlmostEqual(origin['check']['base'], 26076324.10, places=2)
        # Octubre se recalculó el 2026-11-16 con el cuadro nuevo: 3 % → 3.5 %.
        self.assertAlmostEqual(origin['check']['gross'], 912671.34, places=2)
        self.assertAlmostEqual(origin['check']['module'], 890071.92, places=2)
        self.assertAlmostEqual(origin['reversals']['commission_adjustment'], -22599.42, places=2)
        own = [g for g in origin['groups'] if g['label'] == 'Tableta del vendedor']
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]['payment_count'], 66)
        self.assertAlmostEqual(own[0]['commission_base'], 16959359.33, places=2)

    def test_eduardo_protire_unreturned_reversals(self):
        """REC 441 y 364 se reaplicaron a la misma factura (completos); REC 155
        a otra factura completo y REC 292 a otra factura por ₡351,680 de los
        ₡354,976.40 desaplicados, así que le toca esa proporción del reverso."""
        result = self._monthly(EDUARDO, PROTIRE)._sng_analysis_unreturned_reversals()
        payments = self.env['account.payment'].browse([971794, 909840, 873882, 144685])
        by_payment = {row['payment']: row for row in result['rows']}
        self.assertEqual(set(by_payment), set(payments.mapped('name')))
        expected = {
            971794: (True, 598.50, 598.50),
            909840: (True, 4026.55, 4026.55),
            873882: (False, 10649.29, round(10649.29 * 351680.00 / 354976.40, 2)),
            144685: (False, 3342.74, 3342.74),
        }
        for payment in payments:
            row = by_payment[payment.name]
            same, reversed_amount, amount = expected[payment.id]
            self.assertEqual(row['same_invoice'], same, payment.name)
            self.assertAlmostEqual(row['reversed_amount'], reversed_amount, places=2, msg=payment.name)
            self.assertAlmostEqual(row['amount'], amount, places=2, msg=payment.name)
        self.assertAlmostEqual(result['reversed_amount'], 18617.08, places=2)

    def test_eduardo_protire_prior_collections(self):
        """Cinco cobros de septiembre confirmados en octubre: los dos meses
        quedaron al 3.5 % (octubre desde el recálculo del 2026-11-16), así que
        ya no hay diferencia de tasa."""
        result = self._monthly(EDUARDO, PROTIRE)._sng_analysis_prior_collections()
        september = self.env['account.payment'].browse([1074779, 1031740, 996706, 996714, 1075570])
        rows = [row for row in result['rows'] if row['payment'] in september.mapped('name')]
        self.assertEqual(len(rows), 5)
        self.assertAlmostEqual(sum(row['commission_base'] for row in rows), 111534.00, places=2)
        for row in rows:
            self.assertEqual(row['reason'], 'Confirmado tarde')
            self.assertAlmostEqual(row['original_percentage'], 3.5)
            self.assertAlmostEqual(row['difference'], 0.0, delta=0.006)

    def test_eduardo_protire_credit_notes(self):
        """Notas hechas sobre facturas cobradas en octubre (11 al 2026-11-13;
        siguen entrando notas nuevas): ninguna se devolvió en efectivo, así que
        no hay comisión de más; cada nota sale una vez y sus destinos suman su
        total."""
        result = self._monthly(EDUARDO, PROTIRE)._sng_analysis_credit_notes()
        self.assertGreaterEqual(result['credit_note_count'], 11)
        self.assertEqual(len({row['credit_note'] for row in result['rows']}), result['credit_note_count'])
        self.assertGreaterEqual(result['total'], 275637.79)
        self.assertAlmostEqual(result['refunded'], 0.0, places=2)
        self.assertAlmostEqual(result['overpaid'], 0.0, places=2)
        for row in result['rows']:
            self.assertAlmostEqual(
                row['to_invoices'] + row['unapplied'] + row['refunded'] + row['other'], row['total'],
                places=2, msg=row['credit_note'])

    def test_cubillo(self):
        """Los cobros de su tableta llegan con cualquiera de sus dos contactos;
        su único reverso (depósito sin fondos) no se reaplicó."""
        monthly = self._monthly(CUBILLO, SAASA)
        origin = monthly._sng_analysis_origin()
        self.assertAlmostEqual(origin['check']['base'], 15943046.42, places=2)
        self.assertAlmostEqual(origin['check']['module'], 437947.05, places=2)
        own = [g for g in origin['groups'] if g['label'] == 'Tableta del vendedor']
        self.assertEqual(own[0]['payment_count'], 150)
        self.assertFalse(monthly._sng_analysis_unreturned_reversals()['rows'])
        dup = self._monthly(CUBILLO_DUP, SAASA)
        self.assertAlmostEqual(dup._sng_analysis_origin()['check']['base'], 3067463.89, places=2)
        self.assertAlmostEqual(dup._sng_analysis_credit_notes()['overpaid'], 0.0, places=2)
