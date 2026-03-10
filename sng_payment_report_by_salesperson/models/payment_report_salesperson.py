# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PaymentReportSalesperson(models.Model):
    _name = 'payment.report.salesperson'
    _description = 'Reporte de Pagos'
    _auto = False
    _order = 'payment_date desc'

    # Cliente
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    partner_name = fields.Char(string='Nombre del Cliente', readonly=True)

    # Vendedor (del cliente)
    salesperson_id = fields.Many2one('res.partner', string='Vendedor', readonly=True)
    salesperson_name = fields.Char(string='Nombre del Vendedor', readonly=True)

    # Pago
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True)
    payment_date = fields.Date(string='Fecha de Pago', readonly=True)
    payment_amount = fields.Monetary(string='Monto del Pago', readonly=True, currency_field='currency_id')
    payment_reference = fields.Char(string='Referencia de Pago', readonly=True)

    # Factura
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)
    invoice_name = fields.Char(string='Número de Factura', readonly=True)
    invoice_date = fields.Date(string='Fecha de Factura', readonly=True)
    invoice_amount_untaxed = fields.Monetary(string='Monto sin Impuestos', readonly=True, currency_field='currency_id')

    # Cálculos
    days_to_pay = fields.Integer(string='Días para Pago', readonly=True,
                                  help='Días transcurridos desde la emisión de la factura hasta el pago')

    # Estado de reconciliación
    is_reconciled = fields.Boolean(string='Reconciliado', readonly=True,
                                    help='Indica si el pago está reconciliado con una factura')

    # Estado del pago
    payment_state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_process', 'En proceso'),
        ('paid', 'Pagado'),
        ('canceled', 'Cancelada'),
        ('rejected', 'Rechazado'),
    ], string='Estado del Pago', readonly=True)

    # Moneda
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)

    # Filtros
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)

    def init(self):
        """
        Crea la vista SQL para el reporte de pagos.

        Muestra todos los pagos confirmados (posted) de entrada (inbound),
        con o sin reconciliación con facturas.
        """
        # Primero eliminamos la vista si existe
        self.env.cr.execute("DROP VIEW IF EXISTS payment_report_salesperson CASCADE")

        query = """
            CREATE OR REPLACE VIEW payment_report_salesperson AS (
                -- Pagos reconciliados con facturas
                SELECT
                    ROW_NUMBER() OVER (ORDER BY ap.date DESC, ap.id, am.id) as id,

                    -- Cliente
                    rp.id as partner_id,
                    rp.name as partner_name,

                    -- Vendedor (del cliente)
                    rp.assigned_salesperson_id as salesperson_id,
                    rp_salesperson.name as salesperson_name,

                    -- Pago
                    ap.id as payment_id,
                    ap.date as payment_date,
                    COALESCE(apr.amount, ap.amount) as payment_amount,
                    ap.name as payment_reference,

                    -- Factura
                    am.id as invoice_id,
                    am.name as invoice_name,
                    am.invoice_date as invoice_date,
                    am.amount_untaxed as invoice_amount_untaxed,

                    -- Cálculo de días
                    (ap.date - am.invoice_date) as days_to_pay,

                    -- Estado de reconciliación
                    TRUE as is_reconciled,

                    -- Estado del pago
                    ap.state as payment_state,

                    -- Moneda y compañía
                    ap.currency_id as currency_id,
                    ap.company_id as company_id

                FROM account_payment ap

                -- Cliente
                INNER JOIN res_partner rp
                    ON rp.id = ap.partner_id

                -- Vendedor del cliente (LEFT JOIN para incluir pagos sin vendedor)
                LEFT JOIN res_partner rp_salesperson
                    ON rp_salesperson.id = rp.assigned_salesperson_id

                -- Relación payment -> move (a través de account.partial.reconcile)
                INNER JOIN account_move_line aml_payment
                    ON aml_payment.payment_id = ap.id

                INNER JOIN account_partial_reconcile apr
                    ON (apr.debit_move_id = aml_payment.id OR apr.credit_move_id = aml_payment.id)

                INNER JOIN account_move_line aml_invoice
                    ON (aml_invoice.id = apr.debit_move_id OR aml_invoice.id = apr.credit_move_id)
                    AND aml_invoice.id != aml_payment.id

                INNER JOIN account_move am
                    ON am.id = aml_invoice.move_id
                    AND am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'

                WHERE
                    ap.payment_type = 'inbound'

                UNION ALL

                -- Pagos NO reconciliados (sin factura asociada)
                SELECT
                    ROW_NUMBER() OVER (ORDER BY ap.date DESC, ap.id) + 1000000 as id,

                    -- Cliente
                    rp.id as partner_id,
                    rp.name as partner_name,

                    -- Vendedor (del cliente)
                    rp.assigned_salesperson_id as salesperson_id,
                    rp_salesperson.name as salesperson_name,

                    -- Pago
                    ap.id as payment_id,
                    ap.date as payment_date,
                    ap.amount as payment_amount,
                    ap.name as payment_reference,

                    -- Sin factura
                    NULL::integer as invoice_id,
                    NULL::varchar as invoice_name,
                    NULL::date as invoice_date,
                    NULL::numeric as invoice_amount_untaxed,

                    -- Sin días de pago
                    NULL::integer as days_to_pay,

                    -- No reconciliado
                    FALSE as is_reconciled,

                    -- Estado del pago
                    ap.state as payment_state,

                    -- Moneda y compañía
                    ap.currency_id as currency_id,
                    ap.company_id as company_id

                FROM account_payment ap

                -- Cliente
                INNER JOIN res_partner rp
                    ON rp.id = ap.partner_id

                -- Vendedor del cliente (LEFT JOIN para incluir pagos sin vendedor)
                LEFT JOIN res_partner rp_salesperson
                    ON rp_salesperson.id = rp.assigned_salesperson_id

                WHERE
                    ap.payment_type = 'inbound'
                    -- Excluir pagos que ya están en la primera consulta (reconciliados)
                    AND NOT EXISTS (
                        SELECT 1
                        FROM account_move_line aml
                        INNER JOIN account_partial_reconcile apr2
                            ON (apr2.debit_move_id = aml.id OR apr2.credit_move_id = aml.id)
                        WHERE aml.payment_id = ap.id
                    )
            )
        """
        self.env.cr.execute(query)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
        Personaliza el read_group para agregar correctamente los totales.
        """
        res = super(PaymentReportSalesperson, self).read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy
        )

        if 'payment_amount' in fields:
            for line in res:
                if '__domain' in line:
                    lines = self.search(line['__domain'])
                    line['payment_amount'] = sum(lines.mapped('payment_amount'))

        return res
