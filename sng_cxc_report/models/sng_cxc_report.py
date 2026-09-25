# -*- coding: utf-8 -*-
import io
import json
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import json_default

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


def _ensure_backing_table(cr, table_name):
    cr.execute(
        """
        SELECT c.relkind
          FROM pg_class c
          JOIN pg_namespace n
            ON n.oid = c.relnamespace
         WHERE c.relname = %s
           AND n.nspname = 'public'
        """,
        (table_name,),
    )
    row = cr.fetchone()
    if row and row[0] == "v":
        cr.execute('DROP VIEW IF EXISTS "%s" CASCADE' % table_name)
    elif row and row[0] == "m":
        cr.execute('DROP MATERIALIZED VIEW IF EXISTS "%s" CASCADE' % table_name)

    cr.execute(
        'CREATE TABLE IF NOT EXISTS "%s" (id SERIAL PRIMARY KEY)' % table_name
    )


class SngCxcReport(models.Model):
    _name = "sng.cxc.report"
    _description = "Reporte CxC por Cliente"
    _auto = False
    _rec_name = "partner_commercial_name"
    _order = "total_receivable desc, partner_commercial_name"

    user_id = fields.Many2one("res.users", string="Usuario", readonly=True)
    cutoff_date = fields.Date(string="Fecha de corte", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    partner_unique_id = fields.Char(
        string="Codigo de cliente",
        readonly=True,
        help="Codigo tomado de res.partner.unique_id.",
    )
    partner_commercial_name = fields.Char(
        string="Nombre comercial",
        readonly=True,
        help="Nombre tomado de res.partner.commercial_name con fallback a res.partner.name.",
    )
    assigned_salesperson_id = fields.Many2one(
        "res.partner",
        string="Vendedor asignado",
        readonly=True,
        help="Vendedor tomado de res.partner.assigned_salesperson_id.",
    )
    sales_route_id = fields.Many2one(
        "sng.sales.route",
        string="Ruta",
        readonly=True,
        help="Ruta tomada de res.partner.sales_route_id.",
    )
    credit_limit = fields.Monetary(
        string="Limite de credito",
        readonly=True,
        currency_field="currency_id",
    )
    over_limit_amount = fields.Monetary(
        string="Sobrelimite",
        readonly=True,
        currency_field="currency_id",
        help="Limite de credito menos cartera neta. Positivo indica cupo disponible; negativo, exceso sobre el limite.",
    )
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Termino de pago",
        readonly=True,
    )
    payment_term_days = fields.Integer(
        string="Plazo",
        readonly=True,
        help="Dias estimados del termino de pago, calculados a partir del termino del cliente.",
    )
    dpp_days = fields.Float(
        string="DPP (dias)",
        readonly=True,
        digits=(16, 1),
        help="Dias Promedio de Pago calculados por el modulo regalarte_customer_metrics.",
    )
    consignment_value = fields.Monetary(
        string="Valor consignacion",
        readonly=True,
        currency_field="currency_id",
        help="Suma de cantidad × precio de venta (sin impuestos) de todos los productos en la ubicacion asignada al cliente.",
    )
    total_exposure = fields.Monetary(
        string="Cartera neta + Consig.",
        readonly=True,
        currency_field="currency_id",
        help="Cartera neta + valor consignacion. Indica la exposicion total de riesgo con el cliente.",
    )
    last_sale_date = fields.Date(
        string="Ultima venta",
        readonly=True,
        help="Fecha de la ultima factura de cliente publicada del partner.",
    )
    total_receivable = fields.Monetary(
        string="Total por cobrar",
        readonly=True,
        currency_field="currency_id",
        help="Saldo pendiente real a la fecha de corte, calculado sobre lineas por cobrar y conciliaciones parciales hasta esa fecha.",
    )
    not_due_amount = fields.Monetary(
        string="No vencido",
        readonly=True,
        currency_field="currency_id",
        help="Importe pendiente con vencimiento posterior a la fecha de corte.",
    )
    overdue_amount = fields.Monetary(
        string="Vencido origen",
        readonly=True,
        currency_field="currency_id",
        help="Importe pendiente con vencimiento igual o anterior a la fecha de corte.",
    )
    bucket_1_15 = fields.Monetary(
        string="1-15 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_16_30 = fields.Monetary(
        string="16-30 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_1_30 = fields.Monetary(
        string="1-30 dias",
        readonly=True,
        currency_field="currency_id",
        help="Antiguedad calculada desde date_maturity, o date si no existe.",
    )
    bucket_31_45 = fields.Monetary(
        string="31-45 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_46_60 = fields.Monetary(
        string="46-60 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_31_60 = fields.Monetary(
        string="31-60 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_61_90 = fields.Monetary(
        string="61-90 dias",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_91_plus = fields.Monetary(
        string="91+ dias",
        readonly=True,
        currency_field="currency_id",
    )
    gross_receivable = fields.Monetary(
        string="Cartera bruta",
        readonly=True,
        currency_field="currency_id",
    )
    credit_balance = fields.Monetary(
        string="Saldo a favor",
        readonly=True,
        currency_field="currency_id",
    )
    positive_overdue_amount = fields.Monetary(
        string="Vencido positivo",
        readonly=True,
        currency_field="currency_id",
    )
    overdue_ratio = fields.Float(string="% vencido", readonly=True, digits=(16, 6))
    bucket_91_ratio = fields.Float(string="% 91+", readonly=True, digits=(16, 6))
    dominant_bucket = fields.Selection(
        selection=[
            ("not_due", "No vencido"),
            ("bucket_1_15", "1-15"),
            ("bucket_16_30", "16-30"),
            ("bucket_31_45", "31-45"),
            ("bucket_46_60", "46-60"),
            ("bucket_61_90", "61-90"),
            ("bucket_91_plus", "91+"),
        ],
        string="Bucket dominante",
        readonly=True,
    )
    weighted_overdue_days = fields.Integer(string="Dias mora pond.", readonly=True)
    risk_level = fields.Selection(
        selection=[
            ("no_balance", "Sin saldo"),
            ("credit_balance", "Saldo a favor"),
            ("current", "Al dia"),
            ("low", "Bajo"),
            ("medium", "Medio"),
            ("high", "Alto"),
            ("critical", "Critico"),
            ("cleanup_critical", "Depuracion critica"),
            ("strategic_preventive", "Preventivo estrategico"),
        ],
        string="Riesgo",
        readonly=True,
    )
    priority = fields.Selection(
        selection=[
            ("p1", "P1"),
            ("p2", "P2"),
            ("p3", "P3"),
            ("p4", "P4"),
        ],
        string="Prioridad",
        readonly=True,
    )
    recommended_action = fields.Char(string="Accion recomendada", readonly=True)
    suggested_responsible = fields.Char(string="Responsable sugerido", readonly=True)
    credit_restriction = fields.Boolean(string="Restriccion credito", readonly=True)
    inactive_flag = fields.Boolean(string="Flag inactivo", readonly=True)
    no_use_flag = fields.Boolean(string="Flag no usar", readonly=True)
    action_plan_id = fields.Many2one(
        "sng.cxc.action.plan",
        string="Plan de accion",
        readonly=True,
    )
    company_id = fields.Many2one("res.company", string="Compania", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    def init(self):
        _ensure_backing_table(self._cr, "sng_cxc_report")
        column_definitions = {
            "user_id": "INTEGER NOT NULL",
            "cutoff_date": "DATE NOT NULL",
            "partner_id": "INTEGER NOT NULL",
            "partner_unique_id": "VARCHAR",
            "partner_commercial_name": "VARCHAR",
            "assigned_salesperson_id": "INTEGER",
            "sales_route_id": "INTEGER",
            "credit_limit": "NUMERIC",
            "over_limit_amount": "NUMERIC",
            "payment_term_id": "INTEGER",
            "payment_term_days": "INTEGER",
            "dpp_days": "NUMERIC",
            "consignment_value": "NUMERIC",
            "total_exposure": "NUMERIC",
            "last_sale_date": "DATE",
            "total_receivable": "NUMERIC",
            "not_due_amount": "NUMERIC",
            "overdue_amount": "NUMERIC",
            "bucket_1_15": "NUMERIC",
            "bucket_16_30": "NUMERIC",
            "bucket_1_30": "NUMERIC",
            "bucket_31_45": "NUMERIC",
            "bucket_46_60": "NUMERIC",
            "bucket_31_60": "NUMERIC",
            "bucket_61_90": "NUMERIC",
            "bucket_91_plus": "NUMERIC",
            "gross_receivable": "NUMERIC",
            "credit_balance": "NUMERIC",
            "positive_overdue_amount": "NUMERIC",
            "overdue_ratio": "NUMERIC",
            "bucket_91_ratio": "NUMERIC",
            "dominant_bucket": "VARCHAR",
            "weighted_overdue_days": "INTEGER",
            "risk_level": "VARCHAR",
            "priority": "VARCHAR",
            "recommended_action": "VARCHAR",
            "suggested_responsible": "VARCHAR",
            "credit_restriction": "BOOLEAN",
            "inactive_flag": "BOOLEAN",
            "no_use_flag": "BOOLEAN",
            "action_plan_id": "INTEGER",
            "company_id": "INTEGER NOT NULL",
            "currency_id": "INTEGER NOT NULL",
        }
        for column_name, column_type in column_definitions.items():
            self._cr.execute(
                "ALTER TABLE sng_cxc_report ADD COLUMN IF NOT EXISTS %s %s"
                % (column_name, column_type)
            )

        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS sng_cxc_report_user_cutoff_idx
                ON sng_cxc_report (user_id, cutoff_date);
            CREATE INDEX IF NOT EXISTS sng_cxc_report_partner_idx
                ON sng_cxc_report (partner_id);
            CREATE INDEX IF NOT EXISTS sng_cxc_report_company_idx
                ON sng_cxc_report (company_id);
            """
        )

    @api.model
    def _get_allowed_company_ids(self):
        return self.env.context.get("allowed_company_ids") or self.env.companies.ids

    @api.model
    def _get_salesperson_sql_expr(self, company_column):
        """Expresion SQL del vendedor asignado del partner (alias ``rp``).

        En Grupo Famoso ``sales_commission_omax`` define
        ``res.partner.assigned_salesperson_id`` como ``company_dependent``
        (columna jsonb ``{company_id: partner_id}``), asi que el vendedor se
        resuelve con la compania de la linea. Si en otra instancia el campo
        es un Many2one plano, se usa la columna directamente.
        """
        field = self.env["res.partner"]._fields["assigned_salesperson_id"]
        if field.company_dependent:
            return "(rp.assigned_salesperson_id->>(%s::text))::integer" % company_column
        return "rp.assigned_salesperson_id"

    @api.model
    def _get_snapshot_domain(self, cutoff_date=None):
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        return [
            ("cutoff_date", "=", cutoff_date),
            ("company_id", "in", self._get_allowed_company_ids()),
        ]

    @api.model
    def _get_xlsx_action(self, cutoff_date):
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        return {
            "type": "ir.actions.report",
            "data": {
                "model": self._name,
                "options": json.dumps(
                    {"cutoff_date": fields.Date.to_string(cutoff_date)},
                    default=json_default,
                ),
                "output_format": "xlsx",
                "report_name": "cxc_por_cliente_%s" % cutoff_date,
            },
            "report_type": "sng_cxc_report_xlsx",
        }

    @api.model
    def _get_payment_term_days_map(self, term_ids):
        example_date = fields.Date.to_date("2024-01-15")
        days_map = {}
        for term in self.env["account.payment.term"].browse(term_ids):
            company = term.company_id or self.env.company
            currency = company.currency_id
            term_values = term._compute_terms(
                date_ref=example_date,
                currency=currency,
                company=company,
                tax_amount=0.0,
                tax_amount_currency=0.0,
                untaxed_amount=100.0,
                untaxed_amount_currency=100.0,
                sign=1,
            )
            due_days = [
                (line_vals["date"] - example_date).days
                for line_vals in term_values.get("line_ids", [])
                if line_vals.get("date")
            ]
            days_map[term.id] = max(due_days) if due_days else 0
        return days_map

    @api.model
    def _update_payment_term_days(self, cutoff_date, company_ids):
        cutoff_date = fields.Date.to_date(cutoff_date)
        company_ids = tuple(company_ids)
        self._cr.execute(
            """
            SELECT DISTINCT payment_term_id
              FROM sng_cxc_report
             WHERE cutoff_date = %s
               AND company_id IN %s
               AND payment_term_id IS NOT NULL
            """,
            (cutoff_date, company_ids),
        )
        term_ids = [row[0] for row in self._cr.fetchall()]
        if not term_ids:
            return

        days_map = self._get_payment_term_days_map(term_ids)
        for term_id, days in days_map.items():
            self._cr.execute(
                """
                UPDATE sng_cxc_report
                   SET payment_term_days = %s
                 WHERE cutoff_date = %s
                   AND company_id IN %s
                   AND payment_term_id = %s
                """,
                (days, cutoff_date, company_ids, term_id),
            )

    @api.model
    def _rebuild_snapshot(self, cutoff_date):
        """Reconstruye el snapshot CxC para una fecha de corte.

        El snapshot es compartido: la identidad de cada fila es
        (cutoff_date, company_id) y, para el plan de accion,
        (cutoff_date, company_id, partner_id). Regenerar reemplaza el
        snapshot de esas companias para todos los usuarios; user_id se
        guarda solo como auditoria de quien lo genero por ultima vez.
        """
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        company_ids = tuple(self._get_allowed_company_ids())
        if not company_ids:
            raise UserError(_("No hay companias activas para generar el reporte."))

        user_id = self.env.user.id
        salesperson_expr = self._get_salesperson_sql_expr("base_lines.company_id")
        self._cr.execute(
            """
            DELETE FROM sng_cxc_report_line
             WHERE cutoff_date = %s
               AND company_id IN %s
            """,
            (cutoff_date, company_ids),
        )
        self._cr.execute(
            """
            DELETE FROM sng_cxc_report
             WHERE cutoff_date = %s
               AND company_id IN %s
            """,
            (cutoff_date, company_ids),
        )

        detail_sql = """
            WITH part_debit AS (
                SELECT
                    part.debit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %s
                GROUP BY part.debit_move_id
            ),
            part_credit AS (
                SELECT
                    part.credit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %s
                GROUP BY part.credit_move_id
            ),
            base_lines AS (
                SELECT
                    aml.id AS move_line_id,
                    COALESCE(aml.partner_id, am.partner_id) AS partner_id,
                    aml.company_id,
                    am.id AS move_id,
                    am.name AS move_name,
                    am.move_type,
                    COALESCE(am.ref, aml.ref, am.payment_reference) AS ref,
                    am.invoice_date,
                    aml.date AS line_date,
                    COALESCE(aml.date_maturity, aml.date) AS due_date,
                    aml.balance
                        - COALESCE(part_debit.amount, 0)
                        + COALESCE(part_credit.amount, 0) AS open_amount
                FROM account_move_line aml
                JOIN account_move am
                    ON am.id = aml.move_id
                JOIN account_account aa
                    ON aa.id = aml.account_id
                LEFT JOIN part_debit
                    ON part_debit.debit_move_id = aml.id
                LEFT JOIN part_credit
                    ON part_credit.credit_move_id = aml.id
                WHERE aa.account_type = 'asset_receivable'
                  AND am.state = 'posted'
                  AND COALESCE(aml.partner_id, am.partner_id) IS NOT NULL
                  AND aml.company_id IN %s
                  AND aml.date <= %s
            )
            INSERT INTO sng_cxc_report_line (
                user_id,
                cutoff_date,
                partner_id,
                partner_unique_id,
                partner_commercial_name,
                assigned_salesperson_id,
                company_id,
                currency_id,
                move_line_id,
                move_id,
                move_name,
                move_type,
                ref,
                invoice_date,
                line_date,
                due_date,
                open_amount,
                overdue_days,
                aging_bucket
            )
            SELECT
                %s AS user_id,
                %s AS cutoff_date,
                rp.id AS partner_id,
                COALESCE(rp.unique_id, '') AS partner_unique_id,
                COALESCE(NULLIF(rp.commercial_name, ''), rp.name) AS partner_commercial_name,
                {salesperson} AS assigned_salesperson_id,
                base_lines.company_id,
                rc.currency_id,
                base_lines.move_line_id,
                base_lines.move_id,
                base_lines.move_name,
                base_lines.move_type,
                base_lines.ref,
                base_lines.invoice_date,
                base_lines.line_date,
                base_lines.due_date,
                base_lines.open_amount,
                CASE
                    WHEN base_lines.due_date <= %s
                    THEN (%s::date - base_lines.due_date)
                    ELSE 0
                END AS overdue_days,
                CASE
                    WHEN base_lines.due_date > %s THEN 'not_due'
                    WHEN (%s::date - base_lines.due_date) <= 15 THEN 'bucket_1_15'
                    WHEN (%s::date - base_lines.due_date) <= 30 THEN 'bucket_16_30'
                    WHEN (%s::date - base_lines.due_date) <= 45 THEN 'bucket_31_45'
                    WHEN (%s::date - base_lines.due_date) <= 60 THEN 'bucket_46_60'
                    WHEN (%s::date - base_lines.due_date) <= 90 THEN 'bucket_61_90'
                    ELSE 'bucket_91_plus'
                END AS aging_bucket
            FROM base_lines
            JOIN res_partner rp
                ON rp.id = base_lines.partner_id
            JOIN res_company rc
                ON rc.id = base_lines.company_id
            WHERE ROUND(COALESCE(base_lines.open_amount, 0)::numeric, 2) <> 0
        """.format(salesperson=salesperson_expr)
        detail_params = (
            cutoff_date,   # 1  part_debit max_date
            cutoff_date,   # 2  part_credit max_date
            company_ids,   # 3  company_ids IN
            cutoff_date,   # 4  aml.date <=
            user_id,       # 5  user_id
            cutoff_date,   # 6  cutoff_date literal
            cutoff_date,   # 7  overdue_days: due_date <=
            cutoff_date,   # 8  overdue_days: cutoff_date::date - due_date
            cutoff_date,   # 9  bucket: due_date > (not_due)
            cutoff_date,   # 10 bucket: cutoff_date - due_date <= 15
            cutoff_date,   # 11 bucket: cutoff_date - due_date <= 30
            cutoff_date,   # 12 bucket: cutoff_date - due_date <= 45
            cutoff_date,   # 13 bucket: cutoff_date - due_date <= 60
            cutoff_date,   # 14 bucket: cutoff_date - due_date <= 90
        )
        self._cr.execute(detail_sql, detail_params)

        report_sql = """
            WITH part_debit AS (
                SELECT
                    part.debit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %s
                GROUP BY part.debit_move_id
            ),
            part_credit AS (
                SELECT
                    part.credit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %s
                GROUP BY part.credit_move_id
            ),
            base_lines AS (
                SELECT
                    COALESCE(aml.partner_id, am.partner_id) AS partner_id,
                    aml.company_id,
                    COALESCE(aml.date_maturity, aml.date) AS due_date,
                    aml.balance
                        - COALESCE(part_debit.amount, 0)
                        + COALESCE(part_credit.amount, 0) AS open_amount
                FROM account_move_line aml
                JOIN account_move am
                    ON am.id = aml.move_id
                JOIN account_account aa
                    ON aa.id = aml.account_id
                LEFT JOIN part_debit
                    ON part_debit.debit_move_id = aml.id
                LEFT JOIN part_credit
                    ON part_credit.credit_move_id = aml.id
                WHERE aa.account_type = 'asset_receivable'
                  AND am.state = 'posted'
                  AND COALESCE(aml.partner_id, am.partner_id) IS NOT NULL
                  AND aml.company_id IN %s
                  AND aml.date <= %s
            ),
            last_sale AS (
                SELECT
                    am.partner_id,
                    am.company_id,
                    MAX(am.invoice_date) AS last_sale_date
                FROM account_move am
                WHERE am.state = 'posted'
                  AND am.move_type = 'out_invoice'
                  AND am.partner_id IS NOT NULL
                  AND am.company_id IN %s
                  AND COALESCE(am.invoice_date, am.date) <= %s
                GROUP BY am.partner_id, am.company_id
            )
            INSERT INTO sng_cxc_report (
                user_id,
                cutoff_date,
                partner_id,
                partner_unique_id,
                partner_commercial_name,
                assigned_salesperson_id,
                sales_route_id,
                credit_limit,
                payment_term_id,
                payment_term_days,
                dpp_days,
                consignment_value,
                total_exposure,
                last_sale_date,
                total_receivable,
                not_due_amount,
                overdue_amount,
                bucket_1_15,
                bucket_16_30,
                bucket_1_30,
                bucket_31_45,
                bucket_46_60,
                bucket_31_60,
                bucket_61_90,
                bucket_91_plus,
                company_id,
                currency_id
            )
            SELECT
                %s AS user_id,
                %s AS cutoff_date,
                base_lines.partner_id,
                COALESCE(rp.unique_id, '') AS partner_unique_id,
                COALESCE(NULLIF(rp.commercial_name, ''), rp.name) AS partner_commercial_name,
                {salesperson} AS assigned_salesperson_id,
                rp.sales_route_id AS sales_route_id,
                COALESCE(
                    (rp.credit_limit->>(base_lines.company_id::text))::numeric,
                    0.0
                ) AS credit_limit,
                (rp.property_payment_term_id->>(base_lines.company_id::text))::integer AS payment_term_id,
                0 AS payment_term_days,
                COALESCE(rcm.customer_dpp_days, 0.0) AS dpp_days,
                0.0 AS consignment_value,
                0.0 AS total_exposure,
                last_sale.last_sale_date,
                COALESCE(SUM(base_lines.open_amount), 0.0) AS total_receivable,
                COALESCE(SUM(CASE WHEN base_lines.due_date > %s THEN base_lines.open_amount ELSE 0 END), 0.0) AS not_due_amount,
                COALESCE(SUM(CASE WHEN base_lines.due_date <= %s THEN base_lines.open_amount ELSE 0 END), 0.0) AS overdue_amount,
                COALESCE(SUM(CASE WHEN base_lines.due_date <= %s AND (%s::date - base_lines.due_date) <= 15 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_1_15,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) BETWEEN 16 AND 30 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_16_30,
                COALESCE(SUM(CASE WHEN base_lines.due_date <= %s AND (%s::date - base_lines.due_date) <= 30 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_1_30,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) BETWEEN 31 AND 45 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_31_45,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) BETWEEN 46 AND 60 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_46_60,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) BETWEEN 31 AND 60 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_31_60,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) BETWEEN 61 AND 90 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_61_90,
                COALESCE(SUM(CASE WHEN (%s::date - base_lines.due_date) > 90 THEN base_lines.open_amount ELSE 0 END), 0.0) AS bucket_91_plus,
                base_lines.company_id,
                rc.currency_id
            FROM base_lines
            JOIN res_partner rp
                ON rp.id = base_lines.partner_id
            JOIN res_company rc
                ON rc.id = base_lines.company_id
            LEFT JOIN regalarte_customer_metric rcm
                ON rcm.partner_id = base_lines.partner_id
               AND rcm.company_id = base_lines.company_id
            LEFT JOIN last_sale
                ON last_sale.partner_id = base_lines.partner_id
               AND last_sale.company_id = base_lines.company_id
            GROUP BY
                base_lines.partner_id,
                rp.unique_id,
                rp.commercial_name,
                rp.name,
                {salesperson},
                rp.sales_route_id,
                (rp.credit_limit->>(base_lines.company_id::text))::numeric,
                (rp.property_payment_term_id->>(base_lines.company_id::text))::integer,
                rcm.customer_dpp_days,
                last_sale.last_sale_date,
                base_lines.company_id,
                rc.currency_id
        """.format(salesperson=salesperson_expr)
        report_params = (
            cutoff_date,
            cutoff_date,
            company_ids,
            cutoff_date,
            company_ids,
            cutoff_date,
            user_id,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
            cutoff_date,
        )
        self._cr.execute(report_sql, report_params)
        self._cr.execute(
            """
            UPDATE sng_cxc_report
               SET over_limit_amount = COALESCE(credit_limit, 0) - COALESCE(total_receivable, 0)
             WHERE cutoff_date = %s
               AND company_id IN %s
            """,
            (cutoff_date, company_ids),
        )
        self._update_consignment_value(cutoff_date, company_ids)
        self._update_payment_term_days(cutoff_date, company_ids)
        self._update_managerial_fields_and_action_plan(cutoff_date, company_ids)

    @api.model
    def _update_consignment_value(self, cutoff_date, company_ids):
        self._cr.execute(
            """
            UPDATE sng_cxc_report r
               SET consignment_value = COALESCE(sub.val, 0.0)
              FROM (
                    SELECT
                        r2.id,
                        SUM(GREATEST(sq.quantity, 0) * pt.list_price) AS val
                      FROM sng_cxc_report r2
                      JOIN res_partner rp
                        ON rp.id = r2.partner_id
                      JOIN stock_location sl_root
                        ON sl_root.id = rp.sale_location_id
                      JOIN stock_location sl
                        ON sl.parent_path LIKE (sl_root.parent_path || '%%')
                       AND sl.usage = 'internal'
                       AND sl.active = TRUE
                      JOIN stock_quant sq
                        ON sq.location_id = sl.id
                       AND sq.quantity > 0
                       AND sq.company_id = r2.company_id
                      JOIN product_product pp
                        ON pp.id = sq.product_id
                       AND pp.active = TRUE
                      JOIN product_template pt
                        ON pt.id = pp.product_tmpl_id
                       AND pt.active = TRUE
                     WHERE r2.cutoff_date = %s
                       AND r2.company_id IN %s
                     GROUP BY r2.id
                   ) sub
             WHERE r.id = sub.id
            """,
            (cutoff_date, company_ids),
        )

    @api.model
    def _get_priority_defaults(self, priority, generation_date=None):
        generation_date = fields.Date.to_date(generation_date) or fields.Date.context_today(self)
        offsets = {
            "p1": 2,
            "p2": 5,
            "p3": 10,
            "p4": 15,
        }
        return generation_date + timedelta(days=offsets.get(priority, 15))

    @api.model
    def _get_managerial_classification(self, values):
        """Return the initial risk/action policy for one CxC customer row.

        The method is intentionally isolated so thresholds can be adjusted
        without changing the Spreadsheet/dashboard definition.
        """
        gross = values["gross_receivable"]
        credit_balance = values["credit_balance"]
        positive_overdue = values["positive_overdue_amount"]
        overdue_ratio = values["overdue_ratio"]
        bucket_91 = values["bucket_91_plus"]
        bucket_61_90 = values["bucket_61_90"]
        weighted_days = values["weighted_overdue_days"]
        inactive = values["inactive_flag"]
        no_use = values["no_use_flag"]

        if gross <= 0 and credit_balance > 0:
            risk = "credit_balance"
        elif gross <= 0:
            risk = "no_balance"
        elif positive_overdue <= 0:
            risk = "strategic_preventive" if gross >= 2000000 else "current"
        elif (inactive or no_use) and bucket_91 > 0:
            risk = "cleanup_critical"
        elif bucket_91 > 0 or overdue_ratio >= 0.80 or positive_overdue >= 2500000:
            risk = "critical"
        elif bucket_61_90 > 0 or weighted_days >= 46 or overdue_ratio >= 0.50 or positive_overdue >= 1000000:
            risk = "high"
        elif weighted_days >= 16 or overdue_ratio >= 0.15 or positive_overdue >= 300000:
            risk = "medium"
        else:
            risk = "low"

        policy = {
            "critical": (
                "p1",
                _("Bloquear credito, escalar a gerencia y formalizar convenio de pago en 48 horas."),
                _("Jefatura CxC + Gerencia Comercial"),
            ),
            "high": (
                "p1",
                _("Gestion intensiva de cobro; promesa formal de pago, revision de linea y suspension de despachos hasta normalizar."),
                _("CxC + Vendedor"),
            ),
            "cleanup_critical": (
                "p1",
                _("Confirmar estatus comercial, bloquear credito y definir recuperacion o saneamiento contable."),
                _("Jefatura CxC + Comercial"),
            ),
            "medium": (
                "p2",
                _("Llamada de cobro y envio de estado de cuenta; obtener compromiso fechado esta semana."),
                _("Vendedor + CxC"),
            ),
            "low": (
                "p3",
                _("Recordatorio preventivo y confirmacion de pago dentro de 3 a 5 dias."),
                _("Vendedor"),
            ),
            "strategic_preventive": (
                "p3",
                _("Confirmar fecha de pago y enviar estado de cuenta preventivo por alto saldo."),
                _("Vendedor + CxC"),
            ),
            "current": (
                "p4",
                _("Monitoreo preventivo; confirmar proxima fecha de pago."),
                _("Vendedor"),
            ),
            "credit_balance": (
                "p4",
                _("Aplicar nota de credito / compensar saldo y depurar antiguedad. No gestionar cobro."),
                _("CxC + Facturacion"),
            ),
            "no_balance": (
                "p4",
                _("Cerrar caso y dejar cuenta en monitoreo."),
                _("CxC"),
            ),
        }
        priority, action, responsible = policy[risk]
        return {
            "risk_level": risk,
            "priority": priority,
            "recommended_action": action,
            "suggested_responsible": responsible,
            "credit_restriction": priority in ("p1", "p2"),
        }

    @api.model
    def _get_dominant_bucket(self, bucket_values):
        positive_values = {key: value for key, value in bucket_values.items() if value > 0}
        if not positive_values:
            return "not_due"
        return max(positive_values, key=positive_values.get)

    @api.model
    def _get_weighted_overdue_days(self, buckets):
        weighted_buckets = (
            ("bucket_1_15", 8),
            ("bucket_16_30", 23),
            ("bucket_31_45", 38),
            ("bucket_46_60", 53),
            ("bucket_61_90", 75),
            ("bucket_91_plus", 120),
        )
        positive_amounts = [
            (max(0.0, buckets[bucket]), days)
            for bucket, days in weighted_buckets
        ]
        positive_total = sum(amount for amount, __days in positive_amounts)
        if not positive_total:
            return 0
        return round(
            sum(amount * days for amount, days in positive_amounts) / positive_total
        )

    @api.model
    def _update_managerial_fields_and_action_plan(self, cutoff_date, company_ids):
        cutoff_date = fields.Date.to_date(cutoff_date)
        action_plan_model = self.env["sng.cxc.action.plan"].sudo()
        self._cr.execute(
            """
            SELECT
                id,
                partner_id,
                partner_unique_id,
                partner_commercial_name,
                assigned_salesperson_id,
                dpp_days,
                consignment_value,
                total_receivable,
                not_due_amount,
                overdue_amount,
                bucket_1_15,
                bucket_16_30,
                bucket_31_45,
                bucket_46_60,
                bucket_61_90,
                bucket_91_plus,
                company_id,
                currency_id
              FROM sng_cxc_report
             WHERE cutoff_date = %s
               AND company_id IN %s
            """,
            (cutoff_date, tuple(company_ids)),
        )
        rows = self._cr.dictfetchall()
        today = fields.Date.context_today(self)
        salesperson_ids = {row["assigned_salesperson_id"] for row in rows if row["assigned_salesperson_id"]}
        salesperson_names = {
            partner.id: (partner.display_name or "").upper()
            for partner in self.env["res.partner"].browse(salesperson_ids)
        }
        for row in rows:
            total = float(row["total_receivable"] or 0.0)
            buckets = {
                "not_due": float(row["not_due_amount"] or 0.0),
                "bucket_1_15": float(row["bucket_1_15"] or 0.0),
                "bucket_16_30": float(row["bucket_16_30"] or 0.0),
                "bucket_31_45": float(row["bucket_31_45"] or 0.0),
                "bucket_46_60": float(row["bucket_46_60"] or 0.0),
                "bucket_61_90": float(row["bucket_61_90"] or 0.0),
                "bucket_91_plus": float(row["bucket_91_plus"] or 0.0),
            }
            overdue_origin = sum(value for key, value in buckets.items() if key != "not_due")
            # Saldo a favor NETO: lo que le sobra al cliente despues de saldar toda su deuda.
            # Solo es positivo cuando el neto del cliente es negativo (credito > deuda).
            gross = max(0.0, total)
            credit_balance = abs(min(0.0, total))
            positive_overdue = max(0.0, overdue_origin)
            overdue_ratio = positive_overdue / gross if gross else 0.0
            bucket_91_ratio = max(0.0, buckets["bucket_91_plus"]) / gross if gross else 0.0
            weighted_days = self._get_weighted_overdue_days(buckets)
            inactive = "INACT" in (row["partner_commercial_name"] or "").upper()
            salesperson_name = salesperson_names.get(row["assigned_salesperson_id"], "")
            no_use = "NO USAR" in salesperson_name or salesperson_name == "OFICINA"
            values = {
                "gross_receivable": gross,
                "credit_balance": credit_balance,
                "positive_overdue_amount": positive_overdue,
                "overdue_ratio": overdue_ratio,
                "bucket_91_ratio": bucket_91_ratio,
                "dominant_bucket": self._get_dominant_bucket(buckets),
                "weighted_overdue_days": weighted_days,
                "bucket_61_90": buckets["bucket_61_90"],
                "bucket_91_plus": buckets["bucket_91_plus"],
                "inactive_flag": inactive,
                "no_use_flag": no_use,
            }
            values.update(self._get_managerial_classification(values))
            consignment = float(row["consignment_value"] or 0.0)
            total_exposure = total + consignment
            self._cr.execute(
                """
                UPDATE sng_cxc_report
                   SET overdue_amount = %s,
                       gross_receivable = %s,
                       credit_balance = %s,
                       positive_overdue_amount = %s,
                       overdue_ratio = %s,
                       bucket_91_ratio = %s,
                       dominant_bucket = %s,
                       weighted_overdue_days = %s,
                       risk_level = %s,
                       priority = %s,
                       recommended_action = %s,
                       suggested_responsible = %s,
                       credit_restriction = %s,
                       inactive_flag = %s,
                       no_use_flag = %s,
                       total_exposure = %s
                 WHERE id = %s
                """,
                (
                    overdue_origin,
                    gross,
                    credit_balance,
                    positive_overdue,
                    overdue_ratio,
                    bucket_91_ratio,
                    values["dominant_bucket"],
                    weighted_days,
                    values["risk_level"],
                    values["priority"],
                    values["recommended_action"],
                    values["suggested_responsible"],
                    values["credit_restriction"],
                    inactive,
                    no_use,
                    total_exposure,
                    row["id"],
                ),
            )
            plan = action_plan_model.search(
                [
                    ("cutoff_date", "=", cutoff_date),
                    ("company_id", "=", row["company_id"]),
                    ("partner_id", "=", row["partner_id"]),
                ],
                limit=1,
            )
            plan_values = {
                "partner_unique_id": row["partner_unique_id"],
                "partner_commercial_name": row["partner_commercial_name"],
                "assigned_salesperson_id": row["assigned_salesperson_id"],
                "currency_id": row["currency_id"],
                "dpp_days": float(row["dpp_days"] or 0.0),
                "consignment_value": consignment,
                "total_exposure": total_exposure,
                "total_receivable": total,
                "gross_receivable": gross,
                "credit_balance": credit_balance,
                "positive_overdue_amount": positive_overdue,
                "bucket_91_plus": buckets["bucket_91_plus"],
                "overdue_ratio": overdue_ratio,
                "bucket_91_ratio": bucket_91_ratio,
                "dominant_bucket": values["dominant_bucket"],
                "weighted_overdue_days": weighted_days,
                "risk_level": values["risk_level"],
                "priority": values["priority"],
                "recommended_action": values["recommended_action"],
                "suggested_responsible": values["suggested_responsible"],
                "credit_restriction": values["credit_restriction"],
                "inactive_flag": inactive,
                "no_use_flag": no_use,
            }
            if plan:
                plan.write(plan_values)
            else:
                plan_values.update(
                    {
                        "cutoff_date": cutoff_date,
                        "company_id": row["company_id"],
                        "partner_id": row["partner_id"],
                        "state": "pending",
                        "commitment_date": self._get_priority_defaults(values["priority"], today),
                    }
                )
                plan = action_plan_model.create(plan_values)
            self._cr.execute(
                "UPDATE sng_cxc_report SET action_plan_id = %s WHERE id = %s",
                (plan.id, row["id"]),
            )

    def action_open_pending_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos pendientes - %s") % self.partner_commercial_name,
            "res_model": "sng.cxc.report.line",
            "view_mode": "list",
            "views": [(self.env.ref("sng_cxc_report.view_sng_cxc_report_line_tree").id, "list")],
            "domain": [
                ("cutoff_date", "=", self.cutoff_date),
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "search_default_group_by_move_type": 0,
                "create": False,
                "edit": False,
                "delete": False,
            },
            "target": "current",
        }

    def action_open_action_plan(self):
        self.ensure_one()
        if not self.action_plan_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Plan de accion - %s") % self.partner_commercial_name,
            "res_model": "sng.cxc.action.plan",
            "view_mode": "form",
            "res_id": self.action_plan_id.id,
            "target": "current",
        }

    @api.model
    def get_xlsx_report(self, options, response):
        cutoff_date = fields.Date.to_date(options.get("cutoff_date")) or fields.Date.context_today(self)
        records = self.search(self._get_snapshot_domain(cutoff_date))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet(_("CxC por Cliente"))

        title_format = workbook.add_format(
            {"bold": True, "font_size": 16, "align": "center", "valign": "vcenter"}
        )
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#D9E2F3", "border": 1, "align": "center"}
        )
        text_format = workbook.add_format({"border": 1})
        date_format = workbook.add_format({"border": 1, "num_format": "yyyy-mm-dd"})
        amount_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})

        columns = [
            (_("Codigo"), 14, "partner_unique_id", text_format),
            (_("Cliente"), 32, "partner_commercial_name", text_format),
            (_("Vendedor"), 28, "assigned_salesperson_id", text_format),
            (_("Ruta"), 18, "sales_route_id", text_format),
            (_("Ultima venta"), 14, "last_sale_date", date_format),
            (_("Limite de credito"), 16, "credit_limit", amount_format),
            (_("Plazo"), 10, "payment_term_days", text_format),
            (_("DPP (dias)"), 10, "dpp_days", amount_format),
            (_("Saldo a favor"), 14, "credit_balance", amount_format),
            (_("No vencido"), 14, "not_due_amount", amount_format),
            (_("Vencido"), 14, "positive_overdue_amount", amount_format),
            (_("1-15"), 12, "bucket_1_15", amount_format),
            (_("16-30"), 12, "bucket_16_30", amount_format),
            (_("31-45"), 12, "bucket_31_45", amount_format),
            (_("46-60"), 12, "bucket_46_60", amount_format),
            (_("61-90"), 12, "bucket_61_90", amount_format),
            (_("91+"), 12, "bucket_91_plus", amount_format),
            (_("Cartera neta"), 14, "total_receivable", amount_format),
            (_("Valor consig."), 16, "consignment_value", amount_format),
            (_("Cartera+Consig."), 16, "total_exposure", amount_format),
            (_("Sobrelimite"), 14, "over_limit_amount", amount_format),
            (_("Riesgo"), 18, "risk_level", text_format),
            (_("Prioridad"), 10, "priority", text_format),
            (_("Accion recomendada"), 54, "recommended_action", text_format),
        ]

        sheet.merge_range(0, 0, 0, len(columns) - 1, _("Cuentas por Cobrar por Cliente"), title_format)
        sheet.write(1, 0, _("Fecha de corte"), header_format)
        sheet.write(1, 1, fields.Date.to_string(cutoff_date), text_format)

        for col_index, (label, width, field_name, _fmt) in enumerate(columns):
            sheet.set_column(col_index, col_index, width)
            sheet.write(3, col_index, label, header_format)

        row = 4
        for record in records:
            for col_index, (_label, _width, field_name, cell_format) in enumerate(columns):
                value = record[field_name]
                if field_name == "assigned_salesperson_id":
                    value = record.assigned_salesperson_id.display_name or ""
                elif field_name == "sales_route_id":
                    value = record.sales_route_id.display_name or ""
                elif value in (False, None):
                    value = ""
                sheet.write(row, col_index, value, cell_format)
            row += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


class SngCxcReportLine(models.Model):
    _name = "sng.cxc.report.line"
    _description = "Detalle CxC por Documento"
    _auto = False
    _order = "partner_commercial_name, due_date, move_name"

    user_id = fields.Many2one("res.users", string="Usuario", readonly=True)
    cutoff_date = fields.Date(string="Fecha de corte", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    partner_unique_id = fields.Char(string="Codigo", readonly=True)
    partner_commercial_name = fields.Char(string="Nombre comercial", readonly=True)
    assigned_salesperson_id = fields.Many2one("res.partner", string="Vendedor asignado", readonly=True)
    company_id = fields.Many2one("res.company", string="Compania", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    move_line_id = fields.Many2one("account.move.line", string="Apunte", readonly=True)
    move_id = fields.Many2one("account.move", string="Documento", readonly=True)
    move_name = fields.Char(string="Numero", readonly=True)
    move_type = fields.Selection(
        selection=[
            ("entry", "Asiento"),
            ("out_invoice", "Factura cliente"),
            ("out_refund", "Nota de credito"),
            ("out_receipt", "Recibo"),
            ("in_invoice", "Factura proveedor"),
            ("in_refund", "Nota de credito proveedor"),
            ("in_receipt", "Pago proveedor"),
        ],
        string="Tipo",
        readonly=True,
    )
    ref = fields.Char(string="Referencia", readonly=True)
    invoice_date = fields.Date(string="Fecha factura", readonly=True)
    line_date = fields.Date(string="Fecha asiento", readonly=True)
    due_date = fields.Date(string="Vencimiento", readonly=True)
    open_amount = fields.Monetary(
        string="Saldo pendiente",
        readonly=True,
        currency_field="currency_id",
    )
    overdue_days = fields.Integer(string="Dias vencidos", readonly=True)
    aging_bucket = fields.Selection(
        selection=[
            ("not_due", "No vencido"),
            ("bucket_1_15", "1-15"),
            ("bucket_16_30", "16-30"),
            ("bucket_31_45", "31-45"),
            ("bucket_46_60", "46-60"),
            ("bucket_61_90", "61-90"),
            ("bucket_91_plus", "91+"),
        ],
        string="Bucket",
        readonly=True,
    )

    def init(self):
        _ensure_backing_table(self._cr, "sng_cxc_report_line")
        column_definitions = {
            "user_id": "INTEGER NOT NULL",
            "cutoff_date": "DATE NOT NULL",
            "partner_id": "INTEGER NOT NULL",
            "partner_unique_id": "VARCHAR",
            "partner_commercial_name": "VARCHAR",
            "assigned_salesperson_id": "INTEGER",
            "company_id": "INTEGER NOT NULL",
            "currency_id": "INTEGER NOT NULL",
            "move_line_id": "INTEGER NOT NULL",
            "move_id": "INTEGER NOT NULL",
            "move_name": "VARCHAR",
            "move_type": "VARCHAR",
            "ref": "VARCHAR",
            "invoice_date": "DATE",
            "line_date": "DATE",
            "due_date": "DATE",
            "open_amount": "NUMERIC",
            "overdue_days": "INTEGER",
            "aging_bucket": "VARCHAR",
        }
        for column_name, column_type in column_definitions.items():
            self._cr.execute(
                "ALTER TABLE sng_cxc_report_line ADD COLUMN IF NOT EXISTS %s %s"
                % (column_name, column_type)
            )

        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS sng_cxc_report_line_user_cutoff_idx
                ON sng_cxc_report_line (user_id, cutoff_date);
            CREATE INDEX IF NOT EXISTS sng_cxc_report_line_partner_idx
                ON sng_cxc_report_line (partner_id);
            CREATE INDEX IF NOT EXISTS sng_cxc_report_line_company_idx
                ON sng_cxc_report_line (company_id);
            """
        )


class SngCxcActionPlan(models.Model):
    _name = "sng.cxc.action.plan"
    _description = "Plan de Accion CxC"
    _order = "priority, positive_overdue_amount desc, partner_commercial_name"
    _rec_name = "partner_commercial_name"

    cutoff_date = fields.Date(string="Fecha de corte", required=True, index=True)
    company_id = fields.Many2one("res.company", string="Compania", required=True, index=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", required=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True, index=True)
    partner_unique_id = fields.Char(string="Codigo", readonly=True)
    partner_commercial_name = fields.Char(string="Nombre comercial", readonly=True)
    assigned_salesperson_id = fields.Many2one("res.partner", string="Vendedor", readonly=True)
    total_receivable = fields.Monetary(
        string="Cartera neta",
        readonly=True,
        currency_field="currency_id",
    )
    gross_receivable = fields.Monetary(
        string="Cartera bruta",
        readonly=True,
        currency_field="currency_id",
    )
    credit_balance = fields.Monetary(
        string="Saldo a favor",
        readonly=True,
        currency_field="currency_id",
    )
    positive_overdue_amount = fields.Monetary(
        string="Vencido",
        readonly=True,
        currency_field="currency_id",
    )
    bucket_91_plus = fields.Monetary(
        string="91+",
        readonly=True,
        currency_field="currency_id",
    )
    overdue_ratio = fields.Float(string="% vencido", readonly=True, digits=(16, 6))
    bucket_91_ratio = fields.Float(string="% 91+", readonly=True, digits=(16, 6))
    dominant_bucket = fields.Selection(
        selection=[
            ("not_due", "No vencido"),
            ("bucket_1_15", "1-15"),
            ("bucket_16_30", "16-30"),
            ("bucket_31_45", "31-45"),
            ("bucket_46_60", "46-60"),
            ("bucket_61_90", "61-90"),
            ("bucket_91_plus", "91+"),
        ],
        string="Bucket dominante",
        readonly=True,
    )
    weighted_overdue_days = fields.Integer(string="Dias mora pond.", readonly=True)
    dpp_days = fields.Float(string="DPP (dias)", readonly=True, digits=(16, 1))
    consignment_value = fields.Monetary(
        string="Valor consignacion",
        readonly=True,
        currency_field="currency_id",
    )
    total_exposure = fields.Monetary(
        string="Cartera neta + Consig.",
        readonly=True,
        currency_field="currency_id",
    )
    risk_level = fields.Selection(
        selection=[
            ("no_balance", "Sin saldo"),
            ("credit_balance", "Saldo a favor"),
            ("current", "Al dia"),
            ("low", "Bajo"),
            ("medium", "Medio"),
            ("high", "Alto"),
            ("critical", "Critico"),
            ("cleanup_critical", "Depuracion critica"),
            ("strategic_preventive", "Preventivo estrategico"),
        ],
        string="Riesgo",
        readonly=True,
        index=True,
    )
    priority = fields.Selection(
        selection=[
            ("p1", "P1"),
            ("p2", "P2"),
            ("p3", "P3"),
            ("p4", "P4"),
        ],
        string="Prioridad",
        readonly=True,
        index=True,
    )
    recommended_action = fields.Char(string="Accion recomendada", readonly=True)
    suggested_responsible = fields.Char(string="Responsable sugerido", readonly=True)
    credit_restriction = fields.Boolean(string="Restriccion credito", readonly=True)
    inactive_flag = fields.Boolean(string="Flag inactivo", readonly=True)
    no_use_flag = fields.Boolean(string="Flag no usar", readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("contacted", "Contactado"),
            ("promise", "Promesa de pago"),
            ("paid", "Pagado"),
            ("blocked", "Credito bloqueado"),
            ("escalated", "Escalado"),
            ("closed", "Cerrado"),
        ],
        string="Estado",
        default="pending",
        required=True,
        index=True,
    )
    responsible_id = fields.Many2one("res.users", string="Responsable")
    commitment_date = fields.Date(string="Fecha compromiso")
    last_contact_date = fields.Date(string="Fecha ultimo contacto")
    promised_amount = fields.Monetary(
        string="Monto prometido",
        currency_field="currency_id",
    )
    promised_payment_date = fields.Date(string="Fecha promesa pago")
    comments = fields.Text(string="Comentarios")

    is_credit_blocked = fields.Boolean(
        string="Credito bloqueado",
        compute="_compute_is_credit_blocked",
        help="Refleja si el partner tiene el credito bloqueado en este momento.",
    )

    _sql_constraints = [
        (
            "sng_cxc_action_plan_unique",
            "unique(cutoff_date, company_id, partner_id)",
            "Ya existe un plan de accion CxC para este cliente, compania y fecha de corte.",
        )
    ]

    def _compute_is_credit_blocked(self):
        for plan in self:
            plan.is_credit_blocked = plan.partner_id.sng_credit_blocked

    def action_block_credit(self):
        self.ensure_one()
        self.partner_id.sudo().write({"sng_credit_blocked": True})
        self.write({"state": "blocked"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Credito bloqueado"),
                "message": _(
                    "El credito de '%s' ha sido bloqueado. "
                    "Las ordenes de venta seran rechazadas automaticamente."
                )
                % self.partner_commercial_name,
                "type": "warning",
                "sticky": False,
            },
        }

    def action_unblock_credit(self):
        self.ensure_one()
        self.partner_id.sudo().write({"sng_credit_blocked": False})
        if self.state == "blocked":
            self.write({"state": "pending"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Credito liberado"),
                "message": _("El credito de '%s' ha sido liberado.") % self.partner_commercial_name,
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_pending_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos pendientes - %s") % self.partner_commercial_name,
            "res_model": "sng.cxc.report.line",
            "view_mode": "list",
            "views": [(self.env.ref("sng_cxc_report.view_sng_cxc_report_line_tree").id, "list")],
            "domain": [
                ("cutoff_date", "=", self.cutoff_date),
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
            },
            "target": "current",
        }
