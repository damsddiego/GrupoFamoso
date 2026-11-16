# -*- coding: utf-8 -*-
"""Pruebas del barrido: disparo inmediato, aviso de suspenso, limpieza de
sugerencias obsoletas y pagos que no se repiten entre líneas.

Mismas condiciones que test_sng_widget: pensadas para una base restaurada
de prod; los tests que necesitan datos reales se saltan solos si no los
hay. TransactionCase hace rollback.
"""
from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.sng_matching import SNG_AVISO_SUSPENSE


@tagged('post_install', '-at_install', 'sng_barrido')
class TestSngBarrido(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id = [(4, cls.env.ref(
            'sng_conciliacion_bancaria.group_sng_conciliacion').id)]
        cls.Linea = cls.env['account.bank.statement.line']
        cls.cron_barrido = cls.env.ref(
            'sng_conciliacion_bancaria.cron_sng_conciliacion_barrido')

    def _pago_pendiente_unico(self):
        """(diario, candidato) de un pago con transitoria pendiente cuyo
        monto no comparte con ningún otro pendiente del diario ni está ya
        sugerido a otra línea; (None, None) si la base no tiene."""
        self.env.cr.execute("""
            SELECT DISTINCT m.journal_id
            FROM account_payment p
            JOIN account_move m ON m.id = p.move_id AND m.state = 'posted'
            JOIN account_journal j ON j.id = m.journal_id AND j.type = 'bank'
            WHERE p.payment_type = 'inbound'
            ORDER BY m.journal_id
        """)
        for (journal_id,) in self.env.cr.fetchall():
            diario = self.env['account.journal'].browse(journal_id)
            if not diario.suspense_account_id:
                continue
            tomados = self.Linea._sng_pagos_tomados(diario, self.Linea)
            pagos = self.Linea._sng_pagos_pendientes(
                journal_id, fields.Date.to_date('2000-01-01'),
                fields.Date.to_date('2100-01-01'))
            for cands in pagos.values():
                if len(cands) == 1 and cands[0]['pago_id'] not in tomados:
                    return diario, cands[0]
        return None, None

    def _crear_lineas(self, diario, cand, cantidad=1):
        return self.Linea.with_company(diario.company_id).create([{
            'journal_id': diario.id,
            'date': cand['fecha'],
            'payment_ref': 'PRUEBA BARRIDO',
            'amount': cand['monto'],
        } for _i in range(cantidad)])

    def _disparos(self):
        return self.env['ir.cron.trigger'].search_count(
            [('cron_id', '=', self.cron_barrido.id)])

    # ------------------------------------------------------------------
    # Disparo inmediato al crear líneas por cualquier vía
    # ------------------------------------------------------------------
    def test_crear_credito_dispara_barrido(self):
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        antes = self._disparos()
        self._crear_lineas(diario, cand)
        self.assertGreater(self._disparos(), antes,
                           'crear un crédito bancario debe disparar el '
                           'barrido sin esperar la hora')

    def test_crear_con_contexto_no_dispara(self):
        """El importador SNG sugiere en línea: no necesita el barrido."""
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        antes = self._disparos()
        self.Linea.with_context(sng_sin_barrido=True).with_company(
            diario.company_id).create({
                'journal_id': diario.id, 'date': cand['fecha'],
                'payment_ref': 'PRUEBA BARRIDO', 'amount': cand['monto']})
        self.assertEqual(self._disparos(), antes)

    def test_crear_debito_no_dispara(self):
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        antes = self._disparos()
        self.Linea.with_company(diario.company_id).create({
            'journal_id': diario.id, 'date': cand['fecha'],
            'payment_ref': 'PRUEBA BARRIDO', 'amount': -cand['monto']})
        self.assertEqual(self._disparos(), antes)

    # ------------------------------------------------------------------
    # Aviso: suspenso del diario = transitoria de los pagos
    # ------------------------------------------------------------------
    def test_suspense_choca(self):
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        cuenta_pago = self.env['account.move.line'].browse(
            cand['aml_id']).account_id
        otra = self.env['account.account'].search([
            ('company_ids', 'in', diario.company_id.id),
            ('account_type', '=', 'asset_current'),
            ('id', 'not in', (
                cuenta_pago | diario.inbound_payment_method_line_ids
                .payment_account_id).ids),
        ], limit=1)
        if not otra:
            self.skipTest('sin otra cuenta de activo corriente para probar')
        diario.suspense_account_id = otra
        self.assertFalse(self.Linea._sng_suspense_choca(diario))
        linea = self._crear_lineas(diario, cand)
        linea._sng_escribir('pago', cand, 'media', 'motivo de prueba')
        self.assertNotIn(SNG_AVISO_SUSPENSE, linea.sng_motivo)

        metodo = diario.inbound_payment_method_line_ids[:1]
        if not metodo:
            self.skipTest('el diario no tiene método de pago entrante')
        metodo.payment_account_id = cuenta_pago
        diario.suspense_account_id = cuenta_pago
        self.assertTrue(self.Linea._sng_suspense_choca(diario))
        linea._sng_escribir('pago', cand, 'media', 'motivo de prueba')
        self.assertIn(SNG_AVISO_SUSPENSE, linea.sng_motivo,
                      'el motivo debe avisar que no saldrá Validar')

    # ------------------------------------------------------------------
    # Limpieza de sugerencias obsoletas y repetidas
    # ------------------------------------------------------------------
    def test_limpia_sugerencia_de_pago_obsoleta(self):
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        vigente, obsoleta = self._crear_lineas(diario, cand, cantidad=2)
        vigente._sng_escribir('pago', cand, 'alta', 'vigente')
        # 'pago' sin pago: lo que queda cuando el pago se borró o su
        # transitoria ya se concilió por otro lado
        obsoleta.write({'sng_sugerencia': 'pago', 'sng_pago_id': False,
                        'sng_confianza': 'media', 'sng_motivo': 'vieja'})
        self.Linea._sng_limpiar_obsoletas()
        self.assertEqual(vigente.sng_sugerencia, 'pago')
        self.assertEqual(vigente.sng_pago_id.id, cand['pago_id'])
        self.assertFalse(obsoleta.sng_sugerencia)
        self.assertFalse(obsoleta.sng_motivo)

    def test_limpia_pago_repetido_conserva_mejor_confianza(self):
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        media, alta = self._crear_lineas(diario, cand, cantidad=2)
        media._sng_escribir('pago', cand, 'media', 'repetida')
        alta._sng_escribir('pago', cand, 'alta', 'la buena')
        self.Linea._sng_limpiar_obsoletas()
        self.assertEqual(alta.sng_pago_id.id, cand['pago_id'])
        self.assertFalse(media.sng_sugerencia)
        self.assertFalse(media.sng_pago_id)

    def test_sugerir_lote_no_repite_pago(self):
        """Dos depósitos iguales y un solo pago pendiente: el pago se
        sugiere a una sola línea."""
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        lineas = self._crear_lineas(diario, cand, cantidad=2)
        lineas._sng_sugerir_lote()
        con_pago = lineas.filtered(
            lambda l: l.sng_pago_id.id == cand['pago_id'])
        self.assertEqual(len(con_pago), 1,
                         'el mismo pago no puede quedar sugerido en dos '
                         'líneas')

    def test_sugerir_lote_respeta_pago_ya_sugerido(self):
        """Un pago ya sugerido a otra línea pendiente no se vuelve a
        ofrecer en una corrida posterior."""
        diario, cand = self._pago_pendiente_unico()
        if not diario:
            self.skipTest('la base no tiene pago con transitoria pendiente')
        primera, segunda = self._crear_lineas(diario, cand, cantidad=2)
        primera._sng_sugerir_lote()
        self.assertEqual(primera.sng_pago_id.id, cand['pago_id'])
        segunda._sng_sugerir_lote()
        self.assertFalse(segunda.sng_pago_id)
