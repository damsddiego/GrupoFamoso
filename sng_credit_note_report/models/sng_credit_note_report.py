# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools


class SngCreditNoteReport(models.Model):
    """
    Reporte de Notas de Crédito basado en SQL VIEW para máximo rendimiento.

    Este modelo genera una vista SQL que:
    1. Obtiene todas las notas de crédito (account.move con move_type='out_refund')
    2. Extrae información del cliente (partner unique_id y nombre)
    3. Calcula las facturas relacionadas mediante reconciliaciones contables

    LÓGICA DE FACTURAS RELACIONADAS:
    ================================
    Para determinar qué facturas están relacionadas con una nota de crédito, se utilizan
    las reconciliaciones contables (account.partial.reconcile):

    1. Se parte de las líneas contables de la nota de crédito (account.move.line)
    2. Se buscan las reconciliaciones parciales vinculadas (matched_debit_ids / matched_credit_ids)
    3. Se obtienen las líneas contables reconciliadas del lado opuesto
    4. Se identifican los account.move asociados que sean facturas de cliente (out_invoice)
    5. Se agrupan y concatenan los números de factura únicos

    Esta aproximación es más confiable que usar invoice_origin, ya que refleja la realidad
    contable de qué documentos están efectivamente reconciliados.
    """

    _name = 'sng.credit.note.report'
    _description = 'Reporte de Notas de Crédito'
    _auto = False  # No crear tabla, usar SQL VIEW
    _order = 'credit_note_date desc, credit_note_number desc'

    # Campos de identificación
    id = fields.Integer('ID', readonly=True)
    credit_note_id = fields.Many2one('account.move', 'Nota de Crédito', readonly=True)

    # Información del cliente
    partner_id = fields.Many2one('res.partner', 'Cliente', readonly=True)
    partner_unique_id = fields.Char('ID Cliente', readonly=True)
    partner_name = fields.Char('Nombre Cliente', readonly=True)

    # Información de la nota de crédito
    credit_note_number = fields.Char('Número NC', readonly=True)
    credit_note_date = fields.Date('Fecha NC', readonly=True)
    credit_note_amount = fields.Monetary('Monto NC', readonly=True, currency_field='currency_id')
    credit_note_amount_signed = fields.Monetary('Monto NC (Firmado)', readonly=True, currency_field='currency_id')
    reason_ref = fields.Char('Motivo', readonly=True)

    # Estado y compañía
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Publicado'),
        ('cancel', 'Cancelado')
    ], string='Estado', readonly=True)
    company_id = fields.Many2one('res.company', 'Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Moneda', readonly=True)

    # Facturas relacionadas (concatenadas)
    related_invoices = fields.Text('Facturas Relacionadas', readonly=True,
                                   help='Facturas de cliente reconciliadas con esta nota de crédito')

    def init(self):
        """
        Inicializa la vista SQL del reporte.

        La consulta utiliza un CTE (Common Table Expression) para calcular eficientemente
        las facturas relacionadas mediante reconciliaciones, evitando N+1 queries.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)

        # SQL VIEW optimizada con CTE para facturas relacionadas
        query = """
            CREATE OR REPLACE VIEW %s AS (
                WITH credit_note_invoices AS (
                    -- CTE: Obtiene las facturas relacionadas a cada nota de crédito
                    -- mediante reconciliaciones contables
                    SELECT
                        cn_line.move_id AS credit_note_id,
                        STRING_AGG(DISTINCT inv.name, ', ' ORDER BY inv.name) AS related_invoice_numbers
                    FROM account_move_line cn_line
                    -- Reconciliaciones donde la NC es el crédito
                    LEFT JOIN account_partial_reconcile apr_credit
                        ON apr_credit.credit_move_id = cn_line.id
                    LEFT JOIN account_move_line inv_line_from_credit
                        ON inv_line_from_credit.id = apr_credit.debit_move_id
                    LEFT JOIN account_move inv_from_credit
                        ON inv_from_credit.id = inv_line_from_credit.move_id
                        AND inv_from_credit.move_type = 'out_invoice'
                    -- Reconciliaciones donde la NC es el débito
                    LEFT JOIN account_partial_reconcile apr_debit
                        ON apr_debit.debit_move_id = cn_line.id
                    LEFT JOIN account_move_line inv_line_from_debit
                        ON inv_line_from_debit.id = apr_debit.credit_move_id
                    LEFT JOIN account_move inv_from_debit
                        ON inv_from_debit.id = inv_line_from_debit.move_id
                        AND inv_from_debit.move_type = 'out_invoice'
                    -- Consolidar ambas fuentes de facturas
                    LEFT JOIN (
                        SELECT id, name FROM account_move WHERE move_type = 'out_invoice'
                    ) inv ON inv.id = COALESCE(inv_from_credit.id, inv_from_debit.id)
                    WHERE cn_line.move_id IN (
                        SELECT id FROM account_move WHERE move_type = 'out_refund'
                    )
                    GROUP BY cn_line.move_id
                )
                -- Consulta principal: datos de la nota de crédito
                SELECT
                    am.id AS id,
                    am.id AS credit_note_id,
                    am.partner_id AS partner_id,
                    rp.unique_id AS partner_unique_id,
                    rp.name AS partner_name,
                    am.name AS credit_note_number,
                    COALESCE(am.invoice_date, am.date) AS credit_note_date,
                    am.amount_total AS credit_note_amount,
                    am.amount_total_signed AS credit_note_amount_signed,
                    am.ref AS reason_ref,
                    am.state AS state,
                    am.company_id AS company_id,
                    am.currency_id AS currency_id,
                    cni.related_invoice_numbers AS related_invoices
                FROM account_move am
                INNER JOIN res_partner rp ON rp.id = am.partner_id
                LEFT JOIN credit_note_invoices cni ON cni.credit_note_id = am.id
                WHERE am.move_type = 'out_refund'
            )
        """ % (self._table,)

        self.env.cr.execute(query)

    @api.model
    def _read_group_select(self, aggregate_spec, query):
        """Override para permitir agregaciones en campos calculados."""
        return super()._read_group_select(aggregate_spec, query)
