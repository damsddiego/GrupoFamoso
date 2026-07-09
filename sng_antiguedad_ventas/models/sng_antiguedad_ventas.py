# -*- coding: utf-8 -*-
import io
import json

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
          JOIN pg_namespace n ON n.oid = c.relnamespace
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


def _xlsx_cell(row, col):
    name = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return "%s%s" % (name, row + 1)


# Buckets en orden: (campo, día_inicio, día_fin_inclusive, etiqueta)
AGING_BUCKETS = [
    ("bucket_0_30",    0,   30,  "0-30"),
    ("bucket_31_60",   31,  60,  "31-60"),
    ("bucket_61_90",   61,  90,  "61-90"),
    ("bucket_91_120",  91,  120, "91-120"),
    ("bucket_121_150", 121, 150, "121-150"),
    ("bucket_151_180", 151, 180, "151-180"),
    ("bucket_181_210", 181, 210, "181-210"),
    ("bucket_211_240", 211, 240, "211-240"),
    ("bucket_241_270", 241, 270, "241-270"),
    ("bucket_271_300", 271, 300, "271-300"),
    ("bucket_301_330", 301, 330, "301-330"),
    ("bucket_331_360", 331, 360, "331-360"),
    ("bucket_360_plus", 361, None, "360+"),
]


class SngAntiguedadVentas(models.Model):
    _name = "sng.antiguedad.ventas"
    _description = "Antigüedad de Ventas por Cliente"
    _auto = False
    _rec_name = "partner_commercial_name"
    _order = "partner_commercial_name"

    user_id = fields.Many2one("res.users", string="Usuario", readonly=True)
    cutoff_date = fields.Date(string="Fecha de corte", readonly=True)
    num_months = fields.Integer(string="Meses configurados", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    partner_unique_id = fields.Char(string="Código", readonly=True)
    partner_commercial_name = fields.Char(string="Nombre Comercial", readonly=True)
    payment_term_id = fields.Many2one(
        "account.payment.term", string="Plazo", readonly=True
    )
    credit_check = fields.Boolean(string="Crédito activo", readonly=True)
    credit_blocking = fields.Monetary(
        string="Límite de crédito", readonly=True, currency_field="currency_id"
    )
    last_invoice_date = fields.Date(string="F Ultima Factura", readonly=True)
    last_payment_date = fields.Date(string="F Ultimo Pago", readonly=True)
    sales_route_id = fields.Many2one("sng.sales.route", string="Ruta", readonly=True)
    assigned_salesperson_id = fields.Many2one(
        "res.partner", string="Vendedor", readonly=True
    )
    assigned_salesperson_name = fields.Char(string="Vendedor", readonly=True)

    total_receivable = fields.Monetary(
        string="Total", readonly=True, currency_field="currency_id"
    )
    not_due_amount = fields.Monetary(
        string="No vencido", readonly=True, currency_field="currency_id"
    )

    # 12 tramos de 30 días + más de 360
    bucket_0_30 = fields.Monetary(
        string="0-30", readonly=True, currency_field="currency_id"
    )
    bucket_31_60 = fields.Monetary(
        string="31-60", readonly=True, currency_field="currency_id"
    )
    bucket_61_90 = fields.Monetary(
        string="61-90", readonly=True, currency_field="currency_id"
    )
    bucket_91_120 = fields.Monetary(
        string="91-120", readonly=True, currency_field="currency_id"
    )
    bucket_121_150 = fields.Monetary(
        string="121-150", readonly=True, currency_field="currency_id"
    )
    bucket_151_180 = fields.Monetary(
        string="151-180", readonly=True, currency_field="currency_id"
    )
    bucket_181_210 = fields.Monetary(
        string="181-210", readonly=True, currency_field="currency_id"
    )
    bucket_211_240 = fields.Monetary(
        string="211-240", readonly=True, currency_field="currency_id"
    )
    bucket_241_270 = fields.Monetary(
        string="241-270", readonly=True, currency_field="currency_id"
    )
    bucket_271_300 = fields.Monetary(
        string="271-300", readonly=True, currency_field="currency_id"
    )
    bucket_301_330 = fields.Monetary(
        string="301-330", readonly=True, currency_field="currency_id"
    )
    bucket_331_360 = fields.Monetary(
        string="331-360", readonly=True, currency_field="currency_id"
    )
    bucket_360_plus = fields.Monetary(
        string="360+", readonly=True, currency_field="currency_id"
    )

    def init(self):
        _ensure_backing_table(self._cr, "sng_antiguedad_ventas")
        column_definitions = {
            "user_id": "INTEGER NOT NULL",
            "cutoff_date": "DATE NOT NULL",
            "num_months": "INTEGER NOT NULL DEFAULT 12",
            "company_id": "INTEGER NOT NULL",
            "currency_id": "INTEGER NOT NULL",
            "partner_id": "INTEGER NOT NULL",
            "partner_unique_id": "VARCHAR",
            "partner_commercial_name": "VARCHAR",
            "payment_term_id": "INTEGER",
            "credit_check": "BOOLEAN",
            "credit_blocking": "NUMERIC",
            "last_invoice_date": "DATE",
            "last_payment_date": "DATE",
            "sales_route_id": "INTEGER",
            "assigned_salesperson_id": "INTEGER",
            "assigned_salesperson_name": "VARCHAR",
            "total_receivable": "NUMERIC",
            "not_due_amount": "NUMERIC",
            "bucket_0_30": "NUMERIC",
            "bucket_31_60": "NUMERIC",
            "bucket_61_90": "NUMERIC",
            "bucket_91_120": "NUMERIC",
            "bucket_121_150": "NUMERIC",
            "bucket_151_180": "NUMERIC",
            "bucket_181_210": "NUMERIC",
            "bucket_211_240": "NUMERIC",
            "bucket_241_270": "NUMERIC",
            "bucket_271_300": "NUMERIC",
            "bucket_301_330": "NUMERIC",
            "bucket_331_360": "NUMERIC",
            "bucket_360_plus": "NUMERIC",
        }
        for col_name, col_type in column_definitions.items():
            self._cr.execute(
                "ALTER TABLE sng_antiguedad_ventas ADD COLUMN IF NOT EXISTS %s %s"
                % (col_name, col_type)
            )
        self._cr.execute(
            """
            CREATE INDEX IF NOT EXISTS sng_antiguedad_ventas_user_cutoff_idx
                ON sng_antiguedad_ventas (user_id, cutoff_date);
            CREATE INDEX IF NOT EXISTS sng_antiguedad_ventas_partner_idx
                ON sng_antiguedad_ventas (partner_id);
            CREATE INDEX IF NOT EXISTS sng_antiguedad_ventas_company_idx
                ON sng_antiguedad_ventas (company_id);
            CREATE INDEX IF NOT EXISTS sng_antiguedad_ventas_salesperson_idx
                ON sng_antiguedad_ventas (assigned_salesperson_id);
            CREATE INDEX IF NOT EXISTS sng_antiguedad_ventas_route_idx
                ON sng_antiguedad_ventas (sales_route_id);
            """
        )

    @api.model
    def _get_allowed_company_ids(self):
        return self.env.context.get("allowed_company_ids") or self.env.companies.ids

    @api.model
    def _get_snapshot_domain(self, cutoff_date=None):
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        return [
            ("cutoff_date", "=", cutoff_date),
            ("user_id", "=", self.env.user.id),
            ("company_id", "in", self._get_allowed_company_ids()),
        ]

    @api.model
    def _get_xlsx_action(self, cutoff_date, num_months):
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        return {
            "type": "ir.actions.report",
            "data": {
                "model": self._name,
                "options": json.dumps(
                    {
                        "cutoff_date": fields.Date.to_string(cutoff_date),
                        "num_months": num_months,
                        "allowed_company_ids": self._get_allowed_company_ids(),
                    },
                    default=json_default,
                ),
                "output_format": "xlsx",
                "report_name": "antiguedad_ventas_%s" % cutoff_date,
            },
            "report_type": "sng_antiguedad_ventas_xlsx",
        }

    @api.model
    def _rebuild_snapshot(self, cutoff_date, num_months):
        cutoff_date = fields.Date.to_date(cutoff_date) or fields.Date.context_today(self)
        company_ids = tuple(self._get_allowed_company_ids())
        if not company_ids:
            raise UserError(_("No hay compañías activas para generar el reporte."))

        user_id = self.env.user.id

        self._cr.execute(
            """
            DELETE FROM sng_antiguedad_ventas
             WHERE cutoff_date = %s
               AND user_id = %s
               AND company_id IN %s
            """,
            (cutoff_date, user_id, company_ids),
        )

        # Construir las expresiones CASE para cada bucket
        bucket_cases = []
        for field_name, day_from, day_to, _label in AGING_BUCKETS:
            if day_from == 0:
                # 0-30: vencido entre 0 y 30 días (due_date <= cutoff_date AND days <= 30)
                expr = (
                    "COALESCE(SUM(CASE WHEN base_lines.due_date <= %(cd)s::date "
                    "AND (%(cd)s::date - base_lines.due_date) <= 30 "
                    "THEN base_lines.open_amount ELSE 0 END), 0)"
                )
            elif day_to is None:
                # 360+
                expr = (
                    "COALESCE(SUM(CASE WHEN base_lines.due_date <= %(cd)s::date "
                    "AND (%(cd)s::date - base_lines.due_date) > 360 "
                    "THEN base_lines.open_amount ELSE 0 END), 0)"
                )
            else:
                expr = (
                    "COALESCE(SUM(CASE WHEN base_lines.due_date <= %%(cd)s::date "
                    "AND (%%(cd)s::date - base_lines.due_date) BETWEEN %d AND %d "
                    "THEN base_lines.open_amount ELSE 0 END), 0)"
                ) % (day_from, day_to)
            bucket_cases.append((field_name, expr))

        bucket_columns = ",\n                ".join(
            "%s AS %s" % (expr, fname) for fname, expr in bucket_cases
        )

        sql = """
            WITH part_debit AS (
                SELECT
                    part.debit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(cd)s
                GROUP BY part.debit_move_id
            ),
            part_credit AS (
                SELECT
                    part.credit_move_id,
                    SUM(part.amount) AS amount
                FROM account_partial_reconcile part
                WHERE part.max_date <= %(cd)s
                GROUP BY part.credit_move_id
            ),
            last_invoice AS (
                SELECT
                    am.partner_id,
                    am.company_id,
                    MAX(COALESCE(am.invoice_date, am.date)) AS last_invoice_date
                FROM account_move am
                WHERE am.state = 'posted'
                  AND am.move_type = 'out_invoice'
                  AND am.partner_id IS NOT NULL
                  AND am.company_id IN %(companies)s
                  AND COALESCE(am.invoice_date, am.date) <= %(cd)s
                GROUP BY am.partner_id, am.company_id
            ),
            last_payment AS (
                SELECT
                    ap.partner_id,
                    ap.company_id,
                    MAX(ap.date) AS last_payment_date
                FROM account_payment ap
                WHERE ap.state IN ('paid', 'posted')
                  AND ap.payment_type = 'inbound'
                  AND ap.partner_id IS NOT NULL
                  AND ap.company_id IN %(companies)s
                  AND ap.date <= %(cd)s
                GROUP BY ap.partner_id, ap.company_id
            ),
            base_lines AS (
                SELECT
                    COALESCE(aml.partner_id, am.partner_id) AS partner_id,
                    aml.company_id,
                    COALESCE(aml.date_maturity, aml.date)   AS due_date,
                    aml.balance
                        - COALESCE(part_debit.amount, 0)
                        + COALESCE(part_credit.amount, 0)   AS open_amount
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
                  AND aml.company_id IN %(companies)s
                  AND aml.date <= %(cd)s
            )
            INSERT INTO sng_antiguedad_ventas (
                user_id,
                cutoff_date,
                num_months,
                company_id,
                currency_id,
                partner_id,
                partner_unique_id,
                partner_commercial_name,
                payment_term_id,
                credit_check,
                credit_blocking,
                last_invoice_date,
                last_payment_date,
                sales_route_id,
                assigned_salesperson_id,
                assigned_salesperson_name,
                total_receivable,
                not_due_amount,
                """ + ",\n                ".join(fname for fname, _expr in bucket_cases) + """
            )
            SELECT
                %(uid)s                                                        AS user_id,
                %(cd)s                                                         AS cutoff_date,
                %(nm)s                                                         AS num_months,
                base_lines.company_id,
                rc.currency_id,
                base_lines.partner_id,
                COALESCE(rp.unique_id, '')                                     AS partner_unique_id,
                COALESCE(NULLIF(rp.commercial_name, ''), rp.name)             AS partner_commercial_name,
                payment_prop.id                                                AS payment_term_id,
                COALESCE(rp.credit_check, FALSE)                               AS credit_check,
                CASE WHEN COALESCE(rp.credit_check, FALSE)
                     THEN rp.credit_blocking
                     ELSE NULL
                END                                                            AS credit_blocking,
                last_invoice.last_invoice_date,
                last_payment.last_payment_date,
                rp.sales_route_id,
                rp.assigned_salesperson_id,
                salesperson.name                                              AS assigned_salesperson_name,
                COALESCE(SUM(base_lines.open_amount), 0)                       AS total_receivable,
                COALESCE(SUM(CASE WHEN base_lines.due_date > %(cd)s::date
                               THEN base_lines.open_amount ELSE 0 END), 0)     AS not_due_amount,
                """ + bucket_columns + """
            FROM base_lines
            JOIN res_partner rp ON rp.id = base_lines.partner_id
            JOIN res_company rc ON rc.id = base_lines.company_id
            LEFT JOIN res_partner salesperson
                ON salesperson.id = rp.assigned_salesperson_id
            LEFT JOIN LATERAL (
                SELECT NULLIF(
                    rp.property_payment_term_id->>(base_lines.company_id::text),
                    'false'
                )::integer AS id
            ) payment_prop ON TRUE
            LEFT JOIN last_invoice
                ON last_invoice.partner_id = base_lines.partner_id
               AND last_invoice.company_id = base_lines.company_id
            LEFT JOIN last_payment
                ON last_payment.partner_id = base_lines.partner_id
               AND last_payment.company_id = base_lines.company_id
            WHERE ROUND(COALESCE(base_lines.open_amount, 0)::numeric, 2) <> 0
            GROUP BY
                base_lines.company_id,
                rc.currency_id,
                base_lines.partner_id,
                rp.unique_id,
                rp.commercial_name,
                rp.name,
                payment_prop.id,
                rp.credit_check,
                rp.credit_blocking,
                last_invoice.last_invoice_date,
                last_payment.last_payment_date,
                rp.sales_route_id,
                rp.assigned_salesperson_id,
                salesperson.name
        """

        self._cr.execute(sql, {
            "cd": cutoff_date,
            "uid": user_id,
            "nm": num_months,
            "companies": company_ids,
        })

    @api.model
    def get_xlsx_report(self, options, response):
        cutoff_date = fields.Date.to_date(options.get("cutoff_date")) or fields.Date.context_today(self)
        num_months = int(options.get("num_months") or 12)
        num_months = max(1, min(12, num_months))

        records = self.search(self._get_snapshot_domain(cutoff_date))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet(_("Antigüedad de Ventas"))

        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 16, "align": "center", "valign": "vcenter"}
        )
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#D9E2F3", "border": 1, "align": "center"}
        )
        text_fmt = workbook.add_format({"border": 1})
        total_label_fmt = workbook.add_format({"bold": True, "border": 1})
        amount_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        total_amount_fmt = workbook.add_format(
            {"bold": True, "border": 1, "num_format": "#,##0.00"}
        )
        date_fmt = workbook.add_format({"border": 1, "num_format": "dd/mm/yyyy"})

        # Columnas fijas
        fixed_columns = [
            (_("Código"),         14, "partner_unique_id",         text_fmt),
            (_("Nombre Comercial"), 32, "partner_commercial_name",  text_fmt),
            (_("Plazo"),          22, "payment_term_id",           text_fmt),
            (_("Límite de crédito"), 18, "credit_blocking",        amount_fmt),
            (_("F Ultima Factura"), 16, "last_invoice_date",       date_fmt),
            (_("F Ultimo Pago"),  16, "last_payment_date",         date_fmt),
            (_("Ruta"),           18, "sales_route_id",            text_fmt),
            (_("Vendedor"),       28, "assigned_salesperson_name", text_fmt),
            (_("Total"),          14, "total_receivable",          amount_fmt),
        ]

        # Columnas dinámicas según num_months
        dynamic_columns = []
        for i, (field_name, _day_from, _day_to, label) in enumerate(AGING_BUCKETS[:num_months]):
            dynamic_columns.append((_(label), 12, field_name, amount_fmt))

        columns = fixed_columns + dynamic_columns

        sheet.merge_range(
            0, 0, 0, len(columns) - 1, _("Antigüedad de Ventas"), title_fmt
        )
        sheet.write(1, 0, _("Fecha de corte"), header_fmt)
        sheet.write(1, 1, fields.Date.to_string(cutoff_date), text_fmt)

        for col_idx, (label, width, _field, _fmt) in enumerate(columns):
            sheet.set_column(col_idx, col_idx, width)
            sheet.write(3, col_idx, label, header_fmt)

        row = 4
        for record in records:
            for col_idx, (_label, _width, field_name, cell_fmt) in enumerate(columns):
                value = record[field_name]
                if field_name == "sales_route_id":
                    value = record.sales_route_id.name or ""
                elif field_name == "assigned_salesperson_name":
                    value = record.assigned_salesperson_name or ""
                elif field_name == "payment_term_id":
                    value = record.payment_term_id.name or ""
                elif value in (False, None):
                    value = ""
                sheet.write(row, col_idx, value, cell_fmt)
            row += 1

        if records:
            total_row = row
            sheet.write(total_row, 0, _("Total"), total_label_fmt)
            amount_fields = {
                "credit_blocking",
                "total_receivable",
                *(field_name for field_name, _day_from, _day_to, _label in AGING_BUCKETS[:num_months]),
            }
            for col_idx, (_label, _width, field_name, _cell_fmt) in enumerate(columns):
                if field_name in amount_fields:
                    first_cell = _xlsx_cell(4, col_idx)
                    last_cell = _xlsx_cell(total_row - 1, col_idx)
                    sheet.write_formula(
                        total_row,
                        col_idx,
                        "=SUM(%s:%s)" % (first_cell, last_cell),
                        total_amount_fmt,
                    )
                elif col_idx:
                    sheet.write(total_row, col_idx, "", total_label_fmt)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
