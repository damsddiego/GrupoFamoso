# -*- coding: utf-8 -*-
"""Pruebas del aprendizaje de conciliaciones (sng.conciliacion.alias).

Pensadas para correr sobre una base restaurada de prod (prueba_*):
    odoo-bin -c /etc/odoo18.conf -d <bd> --no-http --stop-after-init \
        --test-tags /sng_conciliacion_bancaria
Los tests que necesitan datos reales (líneas de extracto, facturas
abiertas) se saltan solos si la base no los tiene. TransactionCase hace
rollback: la base queda intacta.
"""
from odoo.tests import TransactionCase, tagged

from ..models.sng_matching import _sng_extraer_claves


@tagged('post_install', '-at_install', 'sng_alias')
class TestSngAlias(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id = [(4, cls.env.ref(
            'sng_conciliacion_bancaria.group_sng_conciliacion').id)]
        cls.Alias = cls.env['sng.conciliacion.alias']
        cls.Linea = cls.env['account.bank.statement.line']
        cls.p1, cls.p2, cls.p3 = cls.env['res.partner'].create([
            {'name': 'Cliente Alias Test Uno'},
            {'name': 'Cliente Alias Test Dos'},
            {'name': 'Cliente Alias Test Tres'},
        ])

    # ------------------------------------------------------------------
    # Extracción de claves
    # ------------------------------------------------------------------
    def test_extraer_claves_casos_reales(self):
        casos = {
            'TS SINPE MOVIL Pase-83818770': [('alias_sinpe', 'pase')],
            'TS SINPE MOVIL moto_aventura-8381':
                [('alias_sinpe', 'moto aventura')],
            'TF SINPE_Móvil_Casa_famosa____':
                [('alias_sinpe', 'casa famosa')],
            'TF TEF DE:COMERCIALIZADORA MOTO P':
                [('nombre_tef', 'comercializadora moto p')],
            'TF TEF DE:3101862456 SOCIEDAD ANO':
                [('cedula', '3101862456'),
                 ('nombre_tef', 'sociedad ano')],
            # texto genérico o vacío: nada aprendible
            'TF SINPE_Móvil_Sin_Descripcion': [],
            'TS SINPE MOVIL pago_facturas_-838': [],
            'TS SINPE MOVIL -': [],
            '': [],
            None: [],
        }
        for ref, esperado in casos.items():
            self.assertEqual(_sng_extraer_claves(ref), esperado, ref)

    def test_extraer_claves_nunca_telefonos(self):
        """El teléfono del SINPE es el receptor (de la empresa): jamás
        puede convertirse en clave aprendible."""
        refs = ['TS SINPE MOVIL 83818770', 'TS SINPE MOVIL p-83818770',
                'TS SINPE MOVIL 61234567-83818770']
        for ref in refs:
            for tipo, clave in _sng_extraer_claves(ref):
                self.assertNotRegex(clave.replace(' ', ''),
                                    r'^[24678]\d{7}$', ref)
                if tipo != 'cedula':
                    self.assertFalse(
                        clave.replace(' ', '').isdigit(), ref)

    # ------------------------------------------------------------------
    # Aprender / desaprender / índice
    # ------------------------------------------------------------------
    def test_aprender_upsert_e_indice(self):
        ref = 'TS SINPE MOVIL Pase-83818770'
        self.Alias._sng_aprender(ref, self.p1.id, self.env.company.id, None)
        fila = self.Alias.search([('alias', '=', 'pase'),
                                  ('partner_id', '=', self.p1.id)])
        self.assertEqual(len(fila), 1)
        self.assertEqual(fila.contador, 1)
        self.assertEqual(fila.tipo, 'alias_sinpe')
        self.assertEqual(self.Alias._sng_indice()[('alias_sinpe', 'pase')],
                         (self.p1.id, 1))
        # segundo acierto: upsert, no duplicado
        self.Alias._sng_aprender(ref, self.p1.id, self.env.company.id, None)
        self.assertEqual(fila.contador, 2)
        self.assertEqual(self.Alias.search_count(
            [('alias', '=', 'pase')]), 1)

    def test_desaprender_piso_cero(self):
        ref = 'TS SINPE MOVIL Pase-83818770'
        self.Alias._sng_aprender(ref, self.p1.id, None, None)
        self.Alias._sng_desaprender(ref, self.p1.id)
        fila = self.Alias.search([('alias', '=', 'pase')])
        self.assertEqual(fila.contador, 0)
        self.Alias._sng_desaprender(ref, self.p1.id)  # no baja de 0
        self.assertEqual(fila.contador, 0)
        self.assertNotIn(('alias_sinpe', 'pase'), self.Alias._sng_indice(),
                         'contador 0 no debe sugerirse')

    def test_guard_ambiguedad(self):
        ref = 'TS SINPE MOVIL Kuim-83818770'
        for p in (self.p1, self.p2):
            self.Alias._sng_aprender(ref, p.id, None, None)
        # con 2 partners: fuera del índice pero sigue activo
        self.assertNotIn(('alias_sinpe', 'kuim'), self.Alias._sng_indice())
        self.assertTrue(all(self.Alias.search(
            [('alias', '=', 'kuim')]).mapped('active')))
        # con 3 partners: todo el alias se desactiva
        self.Alias._sng_aprender(ref, self.p3.id, None, None)
        filas = self.Alias.with_context(active_test=False).search(
            [('alias', '=', 'kuim')])
        self.assertEqual(len(filas), 3)
        self.assertFalse(any(filas.mapped('active')))

    # ------------------------------------------------------------------
    # Heurística y _retrieve_partner
    # ------------------------------------------------------------------
    def _linea_sinpe_sin_cedula(self):
        """Línea real sin conciliar cuyo texto da alias SINPE y no trae
        cédula (para que el alias mande)."""
        for linea in self.Linea.search(
                [('is_reconciled', '=', False), ('amount', '>', 0)],
                order='id', limit=300):
            if linea.sng_pago_id \
                    or self.Linea._sng_senales(
                        linea.payment_ref)['cedulas']:
                continue
            claves = [c for c in _sng_extraer_claves(linea.payment_ref)
                      if c[0] == 'alias_sinpe']
            if claves:
                return linea, claves[0]
        return None, None

    def test_heuristica_usa_alias_aprendido(self):
        linea, clave = self._linea_sinpe_sin_cedula()
        if not linea:
            self.skipTest('la base no tiene línea SINPE sin conciliar')
        self.Alias.create({'alias': clave[1], 'tipo': clave[0],
                           'partner_id': self.p1.id, 'contador': 2})
        linea.write({'sng_sugerencia': False, 'sng_confianza': False,
                     'sng_motivo': False, 'partner_id': False})
        linea.accion_sng_sugerir()
        self.assertIn('Alias aprendido', linea.sng_motivo or '')
        self.assertEqual(linea.sng_confianza, 'alta')
        self.assertEqual(linea.partner_id, self.p1)
        self.assertFalse(linea.sng_ia_pendiente,
                         'con alias aprendido no debe ir a la cola IA')

    def test_heuristica_confianza_media_con_un_acierto(self):
        linea, clave = self._linea_sinpe_sin_cedula()
        if not linea:
            self.skipTest('la base no tiene línea SINPE sin conciliar')
        self.Alias.create({'alias': clave[1], 'tipo': clave[0],
                           'partner_id': self.p1.id, 'contador': 1})
        linea.write({'sng_sugerencia': False, 'sng_confianza': False,
                     'sng_motivo': False, 'partner_id': False})
        linea.accion_sng_sugerir()
        self.assertIn('Alias aprendido', linea.sng_motivo or '')
        self.assertEqual(linea.sng_confianza, 'media')

    def test_retrieve_partner_fallback(self):
        linea, clave = self._linea_sinpe_sin_cedula()
        if not linea:
            self.skipTest('la base no tiene línea SINPE sin conciliar')
        self.Alias.create({'alias': clave[1], 'tipo': clave[0],
                           'partner_id': self.p1.id, 'contador': 2})
        nueva = self.Linea.new({
            'payment_ref': linea.payment_ref, 'amount': 100.0,
            'journal_id': linea.journal_id.id,
            'company_id': linea.company_id.id, 'date': linea.date,
        })
        self.assertEqual(nueva._retrieve_partner(), self.p1)

    def test_retrieve_partner_respeta_compania(self):
        linea, clave = self._linea_sinpe_sin_cedula()
        if not linea:
            self.skipTest('la base no tiene línea SINPE sin conciliar')
        otra_cia = self.env['res.company'].search(
            [('id', '!=', linea.company_id.id)], limit=1)
        if not otra_cia:
            self.skipTest('base monocompañía')
        # partner atado a OTRA compañía: el alias no debe autocompletarlo.
        # En este prod company_id es computado desde company_ids
        # (base_multi_company); sin ese módulo es un m2o normal.
        if 'company_ids' in self.p1._fields:
            self.p1.write({'company_ids': [(6, 0, [otra_cia.id])]})
        else:
            self.p1.company_id = otra_cia
        if not self.p1.company_id \
                or self.p1.company_id == linea.company_id:
            self.skipTest('no se pudo atar el partner a otra compañía')
        self.Alias.create({'alias': clave[1], 'tipo': clave[0],
                           'partner_id': self.p1.id, 'contador': 2})
        nueva = self.Linea.new({
            'payment_ref': linea.payment_ref, 'amount': 100.0,
            'journal_id': linea.journal_id.id,
            'company_id': linea.company_id.id, 'date': linea.date,
        })
        self.assertFalse(nueva._retrieve_partner())

    # ------------------------------------------------------------------
    # Hooks de conciliación real (widget) y undo
    # ------------------------------------------------------------------
    def test_widget_aprende_y_undo_desaprende(self):
        linea, clave = self._linea_sinpe_sin_cedula()
        if not linea:
            self.skipTest('la base no tiene línea SINPE sin conciliar')
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
        row = self.env.cr.fetchone()
        if not row:
            self.skipTest('sin factura abierta en la compañía de la línea')
        partner_id, aml_id = row
        aml = self.env['account.move.line'].browse(aml_id)

        widget = self.env['bank.rec.widget'].with_context(
            default_st_line_id=linea.id).new({})
        widget._action_add_new_amls(aml)
        widget._action_validate()
        self.assertTrue(linea.is_reconciled)
        fila = self.Alias.search([('alias', '=', clave[1]),
                                  ('partner_id', '=', partner_id)])
        self.assertEqual(fila.contador, 1,
                         'validar en el widget debe aprender')
        self.assertEqual(fila.origen, 'conciliacion')

        linea.action_undo_reconciliation()
        self.assertFalse(linea.is_reconciled)
        self.assertEqual(fila.contador, 0,
                         'deshacer debe desaprender')

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def test_bootstrap_no_revienta(self):
        res = self.Alias.accion_sng_bootstrap()
        self.assertEqual(res['params']['type'], 'success')
