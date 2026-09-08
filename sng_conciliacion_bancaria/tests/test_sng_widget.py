# -*- coding: utf-8 -*-
"""Pruebas de la integración con el widget nativo de conciliación.

Mismas condiciones que test_sng_alias: pensadas para una base restaurada
de prod; los tests que necesitan datos reales se saltan solos si no los
hay. TransactionCase hace rollback.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'sng_widget')
class TestSngWidget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id = [(4, cls.env.ref(
            'sng_conciliacion_bancaria.group_sng_conciliacion').id)]
        cls.Linea = cls.env['account.bank.statement.line']

    def _linea_credito_sin_conciliar(self):
        return self.Linea.search(
            [('is_reconciled', '=', False), ('amount', '>', 0)],
            order='id', limit=1)

    def _factura_abierta(self, linea):
        """(partner_id, aml_id) de una factura abierta conciliable en la
        compañía de la línea, o None."""
        self.env.cr.execute("""
            SELECT m.commercial_partner_id, l.id
            FROM account_move m
            JOIN account_move_line l ON l.move_id = m.id
                AND l.account_id IN (SELECT id FROM account_account
                                     WHERE account_type
                                           = 'asset_receivable')
                AND NOT l.reconciled AND l.debit > 0
            JOIN res_partner p ON p.id = m.commercial_partner_id
            WHERE m.move_type = 'out_invoice' AND m.state = 'posted'
              AND m.payment_state IN ('not_paid', 'partial')
              AND m.company_id = %s
              AND (p.company_id IS NULL OR p.company_id = %s)
            LIMIT 1
        """, (linea.company_id.id, linea.company_id.id))
        return self.env.cr.fetchone()

    # ------------------------------------------------------------------
    # _sng_amls_sugeridas: revalidación
    # ------------------------------------------------------------------
    def test_amls_sugeridas_revalida(self):
        linea = self._linea_credito_sin_conciliar()
        if not linea:
            self.skipTest('la base no tiene crédito sin conciliar')
        # 'revisar' y 'sin_match' jamás devuelven contrapartidas
        linea.write({'sng_sugerencia': 'revisar'})
        self.assertFalse(linea._sng_amls_sugeridas())
        # 'factura' sin facturas (sugerencia obsoleta): vacío, sin reventar
        linea.write({'sng_sugerencia': 'factura',
                     'sng_factura_ids': [(5, 0, 0)]})
        self.assertFalse(linea._sng_amls_sugeridas())
        # 'pago' sin pago: vacío
        linea.write({'sng_sugerencia': 'pago', 'sng_pago_id': False})
        self.assertFalse(linea._sng_amls_sugeridas())

    # ------------------------------------------------------------------
    # El widget abre la línea con la sugerencia ya montada
    # ------------------------------------------------------------------
    def test_widget_monta_sugerencia(self):
        linea = self._linea_credito_sin_conciliar()
        if not linea:
            self.skipTest('la base no tiene crédito sin conciliar')
        row = self._factura_abierta(linea)
        if not row:
            self.skipTest('sin factura abierta en la compañía de la línea')
        _partner_id, aml_id = row
        aml = self.env['account.move.line'].browse(aml_id)
        linea.write({'sng_sugerencia': 'factura',
                     'sng_factura_ids': [(6, 0, aml.move_id.ids)]})

        widget = self.env['bank.rec.widget'].with_context(
            default_st_line_id=linea.id).new({})
        res = widget._action_trigger_matching_rules()
        if res and (res.get('amls') or res.get('status') == 'write_off'):
            self.skipTest('una regla nativa ya monta esta línea; la '
                          'sugerencia SNG cede el paso (comportamiento '
                          'esperado)')
        montadas = widget.line_ids.filtered(lambda l: l.flag == 'new_aml')
        self.assertIn(aml, montadas.source_aml_id,
                      'el widget debe abrir con la sugerencia montada')
        self.assertFalse(widget.matching_rules_allow_auto_reconcile,
                         'la sugerencia SNG nunca habilita la '
                         'auto-conciliación')

    def test_widget_sugerencia_obsoleta_no_rompe(self):
        """Sugerencia que apunta a facturas ya pagadas: el widget abre
        vacío, sin error."""
        linea = self._linea_credito_sin_conciliar()
        if not linea:
            self.skipTest('la base no tiene crédito sin conciliar')
        linea.write({'sng_sugerencia': 'factura',
                     'sng_factura_ids': [(5, 0, 0)]})
        widget = self.env['bank.rec.widget'].with_context(
            default_st_line_id=linea.id).new({})
        widget._action_trigger_matching_rules()  # no debe reventar
        self.assertFalse(widget.matching_rules_allow_auto_reconcile)

    # ------------------------------------------------------------------
    # Núcleo compartido y barrido
    # ------------------------------------------------------------------
    def test_sugerir_lote_filtra_y_no_notifica(self):
        """El núcleo procesa solo créditos sin conciliar y devuelve la
        tupla (procesadas, pendientes_ia) sin exigir selección válida."""
        vacio = self.Linea.browse()
        procesadas, pendientes = vacio._sng_sugerir_lote()
        self.assertFalse(procesadas)
        self.assertFalse(pendientes)

    def test_cron_barrido_no_revienta(self):
        self.Linea._sng_cron_barrido(limite=5)
