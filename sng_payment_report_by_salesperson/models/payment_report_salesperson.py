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

    # Aplicación del pago (confirmación)
    applied_date = fields.Datetime(
        string='Fecha Aplicación', readonly=True,
        help='Fecha y hora en que el pago fue confirmado (pasó de borrador a '
             'en proceso/pagado), según el registro del chatter. Para pagos '
             'creados ya confirmados (sin transición registrada) se usa la '
             'fecha de creación del pago.')
    applied_user_id = fields.Many2one(
        'res.users', string='Aplicado por', readonly=True,
        help='Usuario que confirmó el pago. Para pagos creados ya confirmados '
             'se usa el usuario que creó el pago.')

    # Factura
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)
    invoice_name = fields.Char(string='Número de Factura', readonly=True)
    invoice_date = fields.Date(string='Fecha de Factura', readonly=True)
    invoice_amount_untaxed = fields.Monetary(string='Monto sin Impuestos', readonly=True, currency_field='currency_id')
    invoice_untaxed_pending = fields.Monetary(
        string='Pendiente sin Impuestos', readonly=True, currency_field='currency_id',
        help='Saldo pendiente sin impuestos de la factura justo antes de aplicar este pago. '
             'En el primer pago equivale al monto total sin impuestos; en los pagos posteriores '
             'disminuye proporcionalmente a lo abonado, en lugar de repetir el monto completo.')
    invoice_untaxed_balance = fields.Monetary(
        string='Saldo sin Impuestos', readonly=True, currency_field='currency_id',
        help='Saldo real de la factura (sin impuestos) DESPUÉS de aplicar este pago. '
             'El pago incluye impuestos y el saldo no, por lo que se descuenta la parte '
             'proporcional neta del pago. Cuando la factura queda totalmente pagada, el saldo es 0.')

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
                -- Última confirmación registrada de cada pago (borrador -> en proceso/pagado),
                -- tomada del tracking del chatter. Las etiquetas están traducidas según el
                -- idioma del usuario que confirmó, por eso se listan en español e inglés.
                WITH pago_confirmacion AS (
                    SELECT DISTINCT ON (mm.res_id)
                        mm.res_id as payment_id,
                        mm.date as applied_date,
                        mm.create_uid as applied_user_id
                    FROM mail_message mm
                    INNER JOIN mail_tracking_value mtv
                        ON mtv.mail_message_id = mm.id
                    INNER JOIN ir_model_fields imf
                        ON imf.id = mtv.field_id
                        AND imf.model = 'account.payment'
                        AND imf.name = 'state'
                    WHERE mm.model = 'account.payment'
                        AND mtv.old_value_char IN ('Borrador', 'Draft')
                        AND mtv.new_value_char IN ('En proceso', 'In Process', 'Pagado', 'Paid')
                    ORDER BY mm.res_id, mm.date DESC, mm.id DESC
                )
                -- Pagos reconciliados con facturas
                SELECT
                    ROW_NUMBER() OVER (ORDER BY ap.date DESC, ap.id, am.id) as id,

                    -- Cliente
                    rp.id as partner_id,
                    rp.name as partner_name,

                    -- Vendedor (del cliente, por empresa del pago)
                    (rp.assigned_salesperson_id->>(ap.company_id::text))::integer as salesperson_id,
                    rp_salesperson.name as salesperson_name,

                    -- Pago
                    ap.id as payment_id,
                    ap.date as payment_date,
                    COALESCE(apr.amount, ap.amount) as payment_amount,
                    ap.name as payment_reference,

                    -- Aplicación del pago (confirmación). Si no hay transición
                    -- registrada (pago creado ya confirmado), se usa la creación.
                    CASE WHEN ap.state IN ('in_process', 'paid')
                         THEN COALESCE(pc.applied_date, ap.create_date)
                    END as applied_date,
                    CASE WHEN ap.state IN ('in_process', 'paid')
                         THEN COALESCE(pc.applied_user_id, ap.create_uid)
                    END as applied_user_id,

                    -- Factura
                    am.id as invoice_id,
                    am.name as invoice_name,
                    am.invoice_date as invoice_date,
                    am.amount_untaxed as invoice_amount_untaxed,

                    -- Pendiente sin impuestos ANTES de este pago (saldo decreciente).
                    -- En el primer abono es el total sin impuestos; en los siguientes
                    -- baja proporcionalmente a lo ya abonado (incluyendo IVA).
                    am.amount_untaxed * (
                        1 - COALESCE(
                            SUM(apr.amount) OVER (
                                PARTITION BY am.id
                                ORDER BY ap.date, ap.id, apr.id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                            ), 0
                        ) / NULLIF(am.amount_total, 0)
                    ) as invoice_untaxed_pending,

                    -- Saldo sin impuestos DESPUÉS de este pago (incluye el abono actual).
                    -- Concilia el pago (con IVA) contra el saldo neto: queda 0 al saldar.
                    am.amount_untaxed * (
                        1 - COALESCE(
                            SUM(apr.amount) OVER (
                                PARTITION BY am.id
                                ORDER BY ap.date, ap.id, apr.id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                            ), 0
                        ) / NULLIF(am.amount_total, 0)
                    ) as invoice_untaxed_balance,

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
                    ON rp_salesperson.id = (rp.assigned_salesperson_id->>(ap.company_id::text))::integer

                -- Confirmación del pago (tracking del chatter)
                LEFT JOIN pago_confirmacion pc
                    ON pc.payment_id = ap.id

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

                    -- Vendedor (del cliente, por empresa del pago)
                    (rp.assigned_salesperson_id->>(ap.company_id::text))::integer as salesperson_id,
                    rp_salesperson.name as salesperson_name,

                    -- Pago
                    ap.id as payment_id,
                    ap.date as payment_date,
                    ap.amount as payment_amount,
                    ap.name as payment_reference,

                    -- Aplicación del pago (confirmación)
                    CASE WHEN ap.state IN ('in_process', 'paid')
                         THEN COALESCE(pc.applied_date, ap.create_date)
                    END as applied_date,
                    CASE WHEN ap.state IN ('in_process', 'paid')
                         THEN COALESCE(pc.applied_user_id, ap.create_uid)
                    END as applied_user_id,

                    -- Sin factura
                    NULL::integer as invoice_id,
                    NULL::varchar as invoice_name,
                    NULL::date as invoice_date,
                    NULL::numeric as invoice_amount_untaxed,
                    NULL::numeric as invoice_untaxed_pending,
                    NULL::numeric as invoice_untaxed_balance,

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
                    ON rp_salesperson.id = (rp.assigned_salesperson_id->>(ap.company_id::text))::integer

                -- Confirmación del pago (tracking del chatter)
                LEFT JOIN pago_confirmacion pc
                    ON pc.payment_id = ap.id

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
