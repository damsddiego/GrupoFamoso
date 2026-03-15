# -*- coding: utf-8 -*-
"""
Wizard principal del reporte "Estado de Cuenta de Clientes".

Responsabilidades:
  1. Capturar filtros del usuario.
  2. Ejecutar consultas SQL optimizadas (máx. 3 queries para todo el reporte).
  3. Proveer datos a tres salidas:
       a) _build_report_lines()  → genera registros persistentes (Ver en pantalla)
       b) _get_report_data()     → dict para PDF (QWeb) y XLSX
  4. REGLA CRÍTICA: Nunca incluir facturas donde state_tributacion == 'Rechazado'.
  5. REGLA CRÍTICA: Pagos en borrador (payment_draft) son informativos solamente.
     NO modifican el saldo contable calculado ni el campo amount_applied.

Estrategia de performance (anti N+1):
  - Query 1: todas las facturas válidas del período/filtros → 1 SQL.
  - Query 2: todas las reconciliaciones de esas facturas → 1 SQL con IN(ids).
  - Query 3: todos los pagos draft de los partners → 1 SQL.
  Total = 3 queries independiente del número de clientes o facturas.
"""

import io
import base64
import logging
from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
AGING_BUCKETS = [
    ('0_30',   '0-30 días',  0,   30),
    ('31_60',  '31-60 días', 31,  60),
    ('61_90',  '61-90 días', 61,  90),
    ('91_plus','91+ días',   91, None),
]


def _aging_bucket(invoice_date, date_due, today=None):
    """
    Calcula el bucket de antigüedad usando fecha de vencimiento.
    Si no hay fecha de vencimiento, usa la fecha de factura.
    Retorna clave del campo: '0_30', '31_60', '61_90' o '91_plus'.
    """
    if today is None:
        today = date.today()
    ref_date = date_due or invoice_date
    if not ref_date:
        return '91_plus'
    days = (today - ref_date).days
    if days <= 30:
        return '0_30'
    if days <= 60:
        return '31_60'
    if days <= 90:
        return '61_90'
    return '91_plus'


class CustomerStatementWizard(models.TransientModel):
    _name = 'sng.customer.statement.wizard'
    _description = 'Wizard: Estado de Cuenta de Clientes'

    # ── Filtros de fecha ────────────────────────────────────────────────────
    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today,
    )

    # ── Filtros de entidades ────────────────────────────────────────────────
    partner_ids = fields.Many2many(
        'res.partner',
        'sng_stmt_wizard_partner_rel',
        'wizard_id', 'partner_id',
        string='Clientes',
        domain="[('customer_rank', '>', 0)]",
        help="Dejar vacío para incluir todos los clientes.",
    )
    company_ids = fields.Many2many(
        'res.company',
        'sng_stmt_wizard_company_rel',
        'wizard_id', 'company_id',
        string='Empresas',
        default=lambda self: self.env.companies,
    )
    salesperson_ids = fields.Many2many(
        'res.partner',
        'sng_stmt_wizard_sales_rel',
        'wizard_id', 'partner_id',
        string='Vendedores',
        domain="[('is_salesperson', '=', True)]",
        help="Filtra por vendedor asignado al cliente (assigned_salesperson_id).",
    )
    tag_ids = fields.Many2many(
        'res.partner.category',
        'sng_stmt_wizard_tag_rel',
        'wizard_id', 'tag_id',
        string='Etiquetas de cliente',
    )

    # ── Opciones ────────────────────────────────────────────────────────────
    currency_display = fields.Selection([
        ('company', 'Moneda de la empresa'),
        ('invoice', 'Moneda de la factura'),
    ], string='Mostrar moneda', default='company')

    report_mode = fields.Selection([
        ('summary', 'Resumen por cliente'),
        ('detail',  'Detalle por cliente (Ledger)'),
    ], string='Modo de reporte', default='summary', required=True)

    include_credit_notes = fields.Boolean(
        string='Incluir notas de crédito',
        default=True,
    )
    show_draft_payments = fields.Boolean(
        string='Mostrar pagos en borrador',
        default=True,
        help="Pagos draft aparecen como 'Pendiente por aplicar' (solo informativo).",
    )
    only_with_balance = fields.Boolean(
        string='Solo con saldo pendiente',
        default=False,
    )
    group_by = fields.Selection([
        ('partner',     'Por cliente'),
        ('company',     'Por empresa'),
        ('salesperson', 'Por vendedor'),
    ], string='Agrupar por', default='partner')

    # ── Descarga XLSX ───────────────────────────────────────────────────────
    excel_file = fields.Binary('Archivo Excel', readonly=True)
    excel_filename = fields.Char('Nombre Excel', readonly=True)

    # ── Validaciones ────────────────────────────────────────────────────────
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from > wiz.date_to:
                raise UserError(_("'Fecha Desde' debe ser anterior a 'Fecha Hasta'."))

    # ======================================================================
    # HELPERS
    # ======================================================================

    def _get_company_ids(self):
        """Retorna IDs de empresa permitidos (intersección con env.companies)."""
        allowed = self.env.companies
        if self.company_ids:
            return list((self.company_ids & allowed).ids)
        return list(allowed.ids)

    def _coerce_translated_text(self, value):
        """
        Convierte un valor de campo traducible leído por SQL a texto plano.
        En Odoo 18 algunos `name` pueden devolverse como dict/json por idioma.
        """
        if isinstance(value, dict):
            lang = self.env.context.get('lang') or self.env.user.lang or 'en_US'
            for key in (lang, 'en_US'):
                txt = value.get(key)
                if txt:
                    return txt
            for txt in value.values():
                if txt:
                    return txt
            return ''
        return value

    def _format_date_dmy(self, value):
        """
        Formatea fechas en formato dia/mes/ano (dd/mm/yyyy).
        Acepta date, datetime o string ISO (yyyy-mm-dd).
        """
        if not value:
            return ''
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ''
            # Si ya viene en formato d/m/y, lo respetamos.
            if len(raw) == 10 and raw[2] == '/' and raw[5] == '/':
                return raw
            parsed = fields.Date.from_string(raw)
            return parsed.strftime('%d/%m/%Y') if parsed else raw
        return str(value)

    # ======================================================================
    # QUERY 1 — Facturas válidas (sin rechazadas por tributación)
    # ======================================================================
    def _fetch_invoices_sql(self):
        """
        Una sola consulta SQL para traer todas las facturas válidas del período.

        EXCLUSIÓN CRÍTICA:
          LOWER(TRIM(COALESCE(am.state_tributacion, ''))) != 'rechazado'
          - COALESCE: maneja NULL (campo no definido o vacío)
          - TRIM: elimina espacios accidentales
          - LOWER: ignora mayúsculas/minúsculas (ej. 'RECHAZADO', 'Rechazado')
          Si el campo state_tributacion no existe en esta instalación, la query
          fallará con un error de columna. En ese caso, eliminar esa cláusula.
        """
        company_ids = self._get_company_ids()
        if not company_ids:
            return []

        move_types = ['out_invoice']
        if self.include_credit_notes:
            move_types.append('out_refund')

        params = {
            'move_types': tuple(move_types),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_ids': tuple(company_ids),
        }

        partner_clause = ''
        if self.partner_ids:
            params['partner_ids'] = tuple(self.partner_ids.ids)
            partner_clause = 'AND am.partner_id IN %(partner_ids)s'

        salesperson_clause = ''
        if self.salesperson_ids:
            params['salesperson_ids'] = tuple(self.salesperson_ids.ids)
            salesperson_clause = 'AND rp.assigned_salesperson_id IN %(salesperson_ids)s'

        tag_clause = ''
        if self.tag_ids:
            params['tag_ids'] = tuple(self.tag_ids.ids)
            tag_clause = """
                AND am.partner_id IN (
                    SELECT partner_id
                    FROM res_partner_res_partner_category_rel
                    WHERE category_id IN %(tag_ids)s
                )
            """

        # Verificar si la columna state_tributacion existe para evitar error SQL
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='account_move' AND column_name='state_tributacion'
        """)
        has_tributacion = bool(self.env.cr.fetchone())
        tributacion_clause = (
            "AND LOWER(TRIM(COALESCE(am.state_tributacion, ''))) != 'rechazado'"
            if has_tributacion else ''
        )

        query = f"""
            SELECT
                am.id                               AS move_id,
                am.name                             AS document_name,
                am.invoice_date                     AS invoice_date,
                am.invoice_date_due                 AS date_due,
                am.partner_id                       AS partner_id,
                rp.name                             AS partner_name,
                rp.vat                              AS partner_vat,
                rp.assigned_salesperson_id          AS salesperson_id,
                rp_sales.name                       AS salesperson_name,
                am.move_type                        AS move_type,
                am.state                            AS state,
                am.payment_state                    AS payment_state,
                am.currency_id                      AS currency_id,
                rc.name                             AS currency_name,
                am.amount_total                     AS amount_total,
                am.amount_residual                  AS amount_residual,
                am.company_id                       AS company_id,
                am.journal_id                       AS journal_id,
                aj.name                             AS journal_name,
                am.ref                              AS reference
            FROM account_move am
            JOIN  res_partner  rp  ON rp.id = am.partner_id
            LEFT JOIN res_partner rp_sales ON rp_sales.id = rp.assigned_salesperson_id
            JOIN  res_currency  rc ON rc.id = am.currency_id
            JOIN  account_journal aj ON aj.id = am.journal_id
            WHERE am.move_type   IN %(move_types)s
              AND am.state        = 'posted'
              AND am.invoice_date >= %(date_from)s
              AND am.invoice_date <= %(date_to)s
              AND am.company_id   IN %(company_ids)s
              {tributacion_clause}
              {partner_clause}
              {salesperson_clause}
              {tag_clause}
            ORDER BY am.partner_id, am.invoice_date, am.name
        """
        self.env.cr.execute(query, params)
        return self.env.cr.dictfetchall()

    # ======================================================================
    # QUERY 2 — Reconciliaciones (pagos aplicados) en bulk
    # ======================================================================
    def _fetch_reconciliations_sql(self, invoice_move_ids):
        """
        Una sola query trae TODOS los pagos aplicados a las facturas recibidas.

        Cómo funciona la reconciliación en Odoo:
          account.partial.reconcile (APR) conecta:
            - debit_move_id  → línea receivable de la FACTURA (la deuda del cliente)
            - credit_move_id → línea del PAGO (disminuye la deuda)
          APR.amount = importe conciliado en la moneda de la empresa

        Por qué esta query y no otra:
          - amount_residual en account.move YA refleja las conciliaciones,
            pero no nos da el detalle de qué pagos se aplicaron.
          - Para el detalle (ledger), necesitamos saber cada pago.
          - Filtramos aml_inv.account_type = 'asset_receivable' para no
            cruzar con otras líneas de la factura (impuestos, ingresos, etc.)

        Retorna: dict {invoice_move_id: {'total_applied': float, 'lines': [...]}}
        """
        if not invoice_move_ids:
            return {}

        self.env.cr.execute("""
            SELECT
                apr.id                                      AS partial_id,
                aml_inv.move_id                             AS invoice_move_id,
                ABS(apr.amount)                             AS applied_amount,
                aml_ctr.move_id                             AS counterpart_move_id,
                am_ctr.name                                 AS counterpart_name,
                am_ctr.date                                 AS counterpart_date,
                am_ctr.ref                                  AS counterpart_ref,
                am_ctr.move_type                            AS counterpart_move_type,
                am_ctr.payment_state                        AS counterpart_payment_state,
                COALESCE(ap_ctr.id, 0)                     AS counterpart_payment_id,
                am_ctr.journal_id                           AS counterpart_journal_id,
                aj.name                                     AS counterpart_journal_name,
                am_ctr.currency_id                          AS counterpart_currency_id,
                rc.name                                     AS counterpart_currency_name,
                COALESCE(
                    NULLIF(ap_ctr.payment_reference, ''),
                    NULLIF(ap_ctr.memo, ''),
                    am_ctr.ref,
                    ''
                )                                           AS counterpart_reference,
                CASE
                    WHEN ap_ctr.id IS NOT NULL THEN 'payment'
                    WHEN am_ctr.move_type = 'out_refund' THEN 'credit_note'
                    ELSE 'other'
                END                                         AS counterpart_kind
            FROM account_partial_reconcile apr
            JOIN account_move_line aml_inv ON aml_inv.id = apr.debit_move_id
            JOIN account_account aa_inv    ON aa_inv.id   = aml_inv.account_id
            JOIN account_move_line aml_ctr ON aml_ctr.id = apr.credit_move_id
            JOIN account_move am_ctr       ON am_ctr.id   = aml_ctr.move_id
            LEFT JOIN account_payment ap_ctr ON ap_ctr.move_id = am_ctr.id
            LEFT JOIN res_currency rc        ON rc.id = am_ctr.currency_id
            LEFT JOIN account_journal aj     ON aj.id = am_ctr.journal_id
            WHERE aml_inv.move_id IN %s
              AND aa_inv.account_type = 'asset_receivable'

            UNION ALL

            SELECT
                apr.id                                      AS partial_id,
                aml_inv.move_id                             AS invoice_move_id,
                ABS(apr.amount)                             AS applied_amount,
                aml_ctr.move_id                             AS counterpart_move_id,
                am_ctr.name                                 AS counterpart_name,
                am_ctr.date                                 AS counterpart_date,
                am_ctr.ref                                  AS counterpart_ref,
                am_ctr.move_type                            AS counterpart_move_type,
                am_ctr.payment_state                        AS counterpart_payment_state,
                COALESCE(ap_ctr.id, 0)                     AS counterpart_payment_id,
                am_ctr.journal_id                           AS counterpart_journal_id,
                aj.name                                     AS counterpart_journal_name,
                am_ctr.currency_id                          AS counterpart_currency_id,
                rc.name                                     AS counterpart_currency_name,
                COALESCE(
                    NULLIF(ap_ctr.payment_reference, ''),
                    NULLIF(ap_ctr.memo, ''),
                    am_ctr.ref,
                    ''
                )                                           AS counterpart_reference,
                CASE
                    WHEN ap_ctr.id IS NOT NULL THEN 'payment'
                    WHEN am_ctr.move_type = 'out_refund' THEN 'credit_note'
                    ELSE 'other'
                END                                         AS counterpart_kind
            FROM account_partial_reconcile apr
            JOIN account_move_line aml_inv ON aml_inv.id = apr.credit_move_id
            JOIN account_account aa_inv    ON aa_inv.id   = aml_inv.account_id
            JOIN account_move_line aml_ctr ON aml_ctr.id = apr.debit_move_id
            JOIN account_move am_ctr       ON am_ctr.id   = aml_ctr.move_id
            LEFT JOIN account_payment ap_ctr ON ap_ctr.move_id = am_ctr.id
            LEFT JOIN res_currency rc        ON rc.id = am_ctr.currency_id
            LEFT JOIN account_journal aj     ON aj.id = am_ctr.journal_id
            WHERE aml_inv.move_id IN %s
              AND aa_inv.account_type = 'asset_receivable'

            ORDER BY invoice_move_id, counterpart_date, partial_id
        """, (tuple(invoice_move_ids), tuple(invoice_move_ids)))

        result = {}
        seen = set()
        for row in self.env.cr.dictfetchall():
            key = (
                row['invoice_move_id'],
                row['partial_id'],
                row['counterpart_move_id'],
                row['applied_amount'],
            )
            if key in seen:
                continue
            seen.add(key)

            row['counterpart_journal_name'] = self._coerce_translated_text(row.get('counterpart_journal_name'))
            row['counterpart_currency_name'] = self._coerce_translated_text(row.get('counterpart_currency_name'))
            row['counterpart_name'] = self._coerce_translated_text(row.get('counterpart_name'))
            row['counterpart_reference'] = self._coerce_translated_text(row.get('counterpart_reference')) or ''

            mid = row['invoice_move_id']
            if mid not in result:
                result[mid] = {'total_applied': 0.0, 'lines': []}
            result[mid]['total_applied'] += row['applied_amount']
            result[mid]['lines'].append(row)
        return result

    # ======================================================================
    # QUERY 3 — Pagos en borrador (solo informativos)
    # ======================================================================
    def _fetch_draft_payments_sql(self, partner_ids, company_ids):
        """
        Detecta account.payment con state='draft' para los clientes dados.

        IMPORTANTE: Estos pagos son SOLO INFORMATIVOS.
          - NO se suman a amount_applied.
          - NO modifican el saldo (residual).
          - Se presentan con la leyenda "Pendiente por aplicar".
          - Solo se muestran si show_draft_payments = True.

        Retorna: dict {partner_id: [row_dict, ...]}
        """
        if not partner_ids or not self.show_draft_payments:
            return {}

        self.env.cr.execute("""
            SELECT
                ap.id           AS payment_id,
                ap.name         AS payment_name,
                ap.date         AS payment_date,
                ap.amount       AS amount,
                ap.partner_id   AS partner_id,
                ap.currency_id  AS currency_id,
                rc.name         AS currency_name,
                ap.journal_id   AS journal_id,
                aj.name         AS journal_name,
                COALESCE(
                    NULLIF(ap.payment_reference, ''),
                    NULLIF(ap.memo, ''),
                    am.ref,
                    ''
                )               AS reference,
                ap.company_id   AS company_id
            FROM account_payment ap
            JOIN res_currency  rc ON rc.id = ap.currency_id
            JOIN account_journal aj ON aj.id = ap.journal_id
            LEFT JOIN account_move am ON am.id = ap.move_id
            WHERE ap.partner_id    IN %s
              AND ap.state          = 'draft'
              AND ap.payment_type   = 'inbound'
              AND ap.company_id     IN %s
            ORDER BY ap.partner_id, ap.date
        """, (tuple(partner_ids), tuple(company_ids)))

        result = {}
        for row in self.env.cr.dictfetchall():
            row['currency_name'] = self._coerce_translated_text(row.get('currency_name'))
            row['journal_name'] = self._coerce_translated_text(row.get('journal_name'))
            row['payment_name'] = self._coerce_translated_text(row.get('payment_name'))
            row['reference'] = self._coerce_translated_text(row.get('reference')) or ''
            pid = row['partner_id']
            result.setdefault(pid, []).append(row)
        return result

    # ======================================================================
    # FUNCIÓN COMÚN: construye estructura de datos normalizada
    # Usada por: _build_report_lines(), _get_report_data() (PDF/XLSX)
    # ======================================================================
    def _compute_report_structure(self):
        """
        Orquesta las 3 queries y devuelve una estructura normalizada de clientes.

        Retorna:
        {
          'customers': [
            {
              'partner_id': int,
              'partner_name': str,
              'partner_vat': str,
              'salesperson_id': int|None,
              'salesperson_name': str,
              'invoices': [         ← líneas de factura/NC con aplicados
                {
                  'type': 'invoice'|'credit_note',
                  'move_id': int,
                  'document_name': str,
                  'invoice_date': date,
                  'date_due': date|None,
                  'journal_id': int,
                  'journal_name': str,
                  'reference': str,
                  'currency_id': int,
                  'currency_name': str,
                  'amount_total': float,   ← firmado (NC negativo)
                  'amount_applied': float,
                  'amount_residual': float,
                  'payment_state': str,
                  'bucket': str,           ← clave de aging
                  'bucket_0_30'...: float, ← saldo en ese bucket (o 0)
                }
              ],
              'draft_payments': [...],  ← solo informativos
              'total_invoiced': float,
              'total_applied': float,
              'total_residual': float,
              'total_draft_pending': float,
              'bucket_0_30': float,
              'bucket_31_60': float,
              'bucket_61_90': float,
              'bucket_91_plus': float,
              'last_invoice_date': date|None,
              'last_payment_date': date|None,
            }
          ],
          'grand_totals': {...},
        }
        """
        invoices_raw = self._fetch_invoices_sql()
        if not invoices_raw:
            raise UserError(_(
                "No se encontraron facturas con los filtros seleccionados.\n"
                "Verifique el rango de fechas, clientes y estado de las facturas."
            ))

        # Agrupar por partner y recolectar todos los move_ids
        invoices_by_partner = {}
        all_move_ids = []
        for inv in invoices_raw:
            pid = inv['partner_id']
            invoices_by_partner.setdefault(pid, []).append(inv)
            all_move_ids.append(inv['move_id'])

        reconciliations = self._fetch_reconciliations_sql(all_move_ids)

        partner_ids_list = list(invoices_by_partner.keys())
        company_ids = self._get_company_ids()
        draft_by_partner = self._fetch_draft_payments_sql(partner_ids_list, company_ids)

        today = date.today()
        customers = []

        for pid, inv_list in invoices_by_partner.items():
            total_invoiced = 0.0
            total_applied = 0.0
            total_residual = 0.0
            buckets = {'0_30': 0.0, '31_60': 0.0, '61_90': 0.0, '91_plus': 0.0}
            last_invoice_date = None
            last_payment_date = None
            invoice_lines = []

            for inv in inv_list:
                is_cn = inv['move_type'] == 'out_refund'
                sign = -1 if is_cn else 1
                amount_total = sign * abs(inv['amount_total'])
                amount_residual = sign * abs(inv['amount_residual'])

                recon = reconciliations.get(inv['move_id'], {})
                applied_lines = sorted(
                    recon.get('lines', []),
                    key=lambda r: (
                        r.get('counterpart_date') or date.min,
                        r.get('partial_id') or 0,
                    ),
                )
                # Evita doble conteo: el aplicado del reporte se calcula en facturas,
                # no en documentos contraparte (NC/reversiones).
                amount_applied = 0.0 if is_cn else recon.get('total_applied', 0.0)

                total_invoiced += amount_total
                total_applied += amount_applied
                total_residual += amount_residual

                if inv['invoice_date']:
                    if last_invoice_date is None or inv['invoice_date'] > last_invoice_date:
                        last_invoice_date = inv['invoice_date']

                for r in applied_lines:
                    pdate = r.get('counterpart_date')
                    if pdate and (last_payment_date is None or pdate > last_payment_date):
                        last_payment_date = pdate

                # Aging: solo facturas con residual > 0
                bucket_key = 'na'
                bkt_vals = {'0_30': 0.0, '31_60': 0.0, '61_90': 0.0, '91_plus': 0.0}
                if not is_cn and amount_residual > 0:
                    bucket_key = _aging_bucket(inv['invoice_date'], inv['date_due'], today)
                    buckets[bucket_key] += amount_residual
                    bkt_vals[bucket_key] = amount_residual

                invoice_lines.append({
                    'type': 'credit_note' if is_cn else 'invoice',
                    'move_id': inv['move_id'],
                    'document_name': inv['document_name'],
                    'invoice_date': inv['invoice_date'],
                    'date_due': inv['date_due'],
                    'journal_id': inv['journal_id'],
                    'journal_name': self._coerce_translated_text(inv['journal_name']),
                    'reference': inv['reference'] or '',
                    'currency_id': inv['currency_id'],
                    'currency_name': self._coerce_translated_text(inv['currency_name']),
                    'amount_total': amount_total,
                    'amount_applied': amount_applied,
                    'amount_residual': amount_residual,
                    'applied_lines': applied_lines if not is_cn else [],
                    'payment_state': inv['payment_state'],
                    'bucket': bucket_key,
                    'bucket_0_30': bkt_vals['0_30'],
                    'bucket_31_60': bkt_vals['31_60'],
                    'bucket_61_90': bkt_vals['61_90'],
                    'bucket_91_plus': bkt_vals['91_plus'],
                })

            draft_pmts = draft_by_partner.get(pid, [])
            total_draft_pending = sum(p['amount'] for p in draft_pmts)

            if self.only_with_balance and total_residual <= 0:
                continue

            p0 = inv_list[0]
            customers.append({
                'partner_id': pid,
                'partner_name': p0['partner_name'],
                'partner_vat': p0['partner_vat'] or '',
                'salesperson_id': p0['salesperson_id'],
                'salesperson_name': p0['salesperson_name'] or '',
                'invoices': invoice_lines,
                'draft_payments': draft_pmts,
                'total_invoiced': total_invoiced,
                'total_applied': total_applied,
                'total_residual': total_residual,
                'total_draft_pending': total_draft_pending,
                'bucket_0_30': buckets['0_30'],
                'bucket_31_60': buckets['31_60'],
                'bucket_61_90': buckets['61_90'],
                'bucket_91_plus': buckets['91_plus'],
                'last_invoice_date': last_invoice_date,
                'last_payment_date': last_payment_date,
            })

        if not customers:
            raise UserError(_(
                "No hay datos para mostrar con los filtros seleccionados. "
                "Pruebe ampliando el rango de fechas o quitando el filtro "
                "'Solo con saldo pendiente'."
            ))

        grand_totals = {
            'total_invoiced':      sum(c['total_invoiced'] for c in customers),
            'total_applied':       sum(c['total_applied'] for c in customers),
            'total_residual':      sum(c['total_residual'] for c in customers),
            'total_draft_pending': sum(c['total_draft_pending'] for c in customers),
            'bucket_0_30':         sum(c['bucket_0_30'] for c in customers),
            'bucket_31_60':        sum(c['bucket_31_60'] for c in customers),
            'bucket_61_90':        sum(c['bucket_61_90'] for c in customers),
            'bucket_91_plus':      sum(c['bucket_91_plus'] for c in customers),
            'customer_count':      len(customers),
        }
        return {'customers': customers, 'grand_totals': grand_totals}

    # ======================================================================
    # ACCIÓN 1: VER EN PANTALLA (nueva)
    # ======================================================================
    def action_view_report(self):
        """
        Genera registros persistentes customer.statement.report[.line]
        y abre una vista tree/pivot sobre las líneas.

        Flujo:
          1. Eliminar reportes previos del mismo usuario (evita acumulación).
          2. Crear cabecera customer.statement.report con los filtros.
          3. Generar líneas según _compute_report_structure() y modo.
          4. Retornar ir.actions.act_window abriendo las líneas.
        """
        self.ensure_one()
        structure = self._compute_report_structure()
        company = self.env.company

        # Limpiar reportes viejos del usuario (borra líneas por cascade)
        old_reports = self.env['customer.statement.report'].search([
            ('create_uid', '=', self.env.uid),
        ])
        old_reports.unlink()

        # Crear cabecera
        report = self.env['customer.statement.report'].create({
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': company.id,
            'mode': self.report_mode,
            'currency_mode': self.currency_display,
            'include_credit_notes': self.include_credit_notes,
            'show_draft_payments': self.show_draft_payments,
            'only_with_balance': self.only_with_balance,
            'partner_ids': [(6, 0, self.partner_ids.ids)],
            'salesperson_ids': [(6, 0, self.salesperson_ids.ids)],
            'tag_ids': [(6, 0, self.tag_ids.ids)],
        })

        # Generar líneas
        if self.report_mode == 'detail':
            self._create_detail_report_lines(report, structure, company)
        else:
            lines_to_create = self._build_report_lines(report, structure, company)
            if lines_to_create:
                # create() en bulk — una sola INSERT masiva
                self.env['customer.statement.report.line'].create(lines_to_create)

        # Abrir vista de líneas
        return {
            'type': 'ir.actions.act_window',
            'name': _('Estado de Cuenta — %s al %s') % (self.date_from, self.date_to),
            'res_model': 'customer.statement.report.line',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('report_id', '=', report.id)],
            'context': {
                'default_report_id': report.id,
                'search_default_group_partner': 1,
            },
            'target': 'current',
        }

    def _build_report_lines(self, report, structure, company):
        """
        Convierte la estructura normalizada en una lista de vals para create() bulk.

        Modo RESUMEN: 1 línea por cliente con totales/KPIs.
        Modo DETALLE: N líneas por cliente:
          - 1 por factura/NC
          - 1 por pago en borrador (entry_type='payment_draft', solo informativo)

        NOTA IMPORTANTE sobre pagos draft:
          - amount_applied = 0  (no se aplica contablemente)
          - residual = 0        (no modifica saldo)
          - amount_pending_draft = monto del pago (campo informativo)
          - legend = 'Pendiente por aplicar'
        """
        lines = []
        today = date.today()
        sequence = 10

        for cust in structure['customers']:
            pid = cust['partner_id']
            sid = cust['salesperson_id']

            if self.report_mode == 'summary':
                # ── Una línea de resumen por cliente ───────────────────────
                lines.append({
                    'report_id': report.id,
                    'company_id': company.id,
                    'partner_id': pid,
                    'salesperson_id': sid,
                    'date': self.date_to,
                    'entry_type': 'invoice',        # Línea de resumen tipificada como factura
                    'document': cust['partner_name'],
                    'reference': '',
                    'currency_id': company.currency_id.id,
                    'amount_total': cust['total_invoiced'],
                    'amount_applied': cust['total_applied'],
                    'residual': cust['total_residual'],
                    'amount_pending_draft': cust['total_draft_pending'],
                    'legend': '',
                    'bucket_aging': 'na',
                    'bucket_0_30': cust['bucket_0_30'],
                    'bucket_31_60': cust['bucket_31_60'],
                    'bucket_61_90': cust['bucket_61_90'],
                    'bucket_91_plus': cust['bucket_91_plus'],
                    'payment_state': '',
                    'level': 0,
                    'sequence': sequence,
                })
                sequence += 1

                # Línea separada para draft si hay
                if self.show_draft_payments and cust['total_draft_pending'] > 0:
                    lines.append({
                        'report_id': report.id,
                        'company_id': company.id,
                        'partner_id': pid,
                        'salesperson_id': sid,
                        'date': today,
                        'entry_type': 'payment_draft',
                        'document': _('Pagos en borrador'),
                        'reference': '',
                        'currency_id': company.currency_id.id,
                        'amount_total': 0.0,
                        'amount_applied': 0.0,    # NUNCA modifica saldo
                        'residual': 0.0,
                        'amount_pending_draft': cust['total_draft_pending'],
                        'legend': _('Pendiente por aplicar'),
                        'bucket_aging': 'na',
                        'bucket_0_30': 0.0,
                        'bucket_31_60': 0.0,
                        'bucket_61_90': 0.0,
                        'bucket_91_plus': 0.0,
                        'payment_state': 'draft',
                        'level': 0,
                        'sequence': sequence,
                    })
                    sequence += 1

            else:
                # ── Modo detalle: línea por factura/NC ─────────────────────
                for inv in cust['invoices']:
                    lines.append({
                        'report_id': report.id,
                        'company_id': company.id,
                        'partner_id': pid,
                        'salesperson_id': sid,
                        'date': inv['invoice_date'],
                        'date_due': inv['date_due'],
                        'entry_type': inv['type'],
                        'move_id': inv['move_id'],
                        'journal_id': inv['journal_id'],
                        'document': inv['document_name'],
                        'reference': inv['reference'],
                        'currency_id': inv['currency_id'],
                        'amount_total': inv['amount_total'],
                        'amount_applied': inv['amount_applied'],
                        'residual': inv['amount_residual'],
                        'amount_pending_draft': 0.0,
                        'legend': '',
                        'bucket_aging': inv['bucket'] if inv['bucket'] != 'na' else 'na',
                        'bucket_0_30': inv['bucket_0_30'],
                        'bucket_31_60': inv['bucket_31_60'],
                        'bucket_61_90': inv['bucket_61_90'],
                        'bucket_91_plus': inv['bucket_91_plus'],
                        'payment_state': inv['payment_state'],
                    })

                # ── Pagos en borrador: línea por pago, SOLO INFORMATIVO ────
                if self.show_draft_payments:
                    for dp in cust['draft_payments']:
                        lines.append({
                            'report_id': report.id,
                            'company_id': company.id,
                            'partner_id': pid,
                            'salesperson_id': sid,
                            'date': dp.get('payment_date'),
                            'date_due': None,
                            'entry_type': 'payment_draft',
                            'move_id': False,
                            'payment_id': dp['payment_id'],
                            'journal_id': dp['journal_id'],
                            'document': dp['payment_name'] or '',
                            'reference': dp.get('reference') or '',
                            'currency_id': dp['currency_id'],
                            # Importes CERO para no afectar saldo contable
                            'amount_total': 0.0,
                            'amount_applied': 0.0,
                            'residual': 0.0,
                            'amount_pending_draft': dp['amount'],
                            'legend': _('Pendiente por aplicar'),
                            'bucket_aging': 'na',
                            'bucket_0_30': 0.0,
                            'bucket_31_60': 0.0,
                            'bucket_61_90': 0.0,
                            'bucket_91_plus': 0.0,
                            'payment_state': 'draft',
                        })

        return lines

    def _create_detail_report_lines(self, report, structure, company):
        """
        Genera jerarquía en modo detalle:
          - Padre: factura
          - Hijos: pagos/NC/reversiones aplicadas por conciliación parcial
          - Pagos en borrador quedan separados como líneas independientes
        """
        line_obj = self.env['customer.statement.report.line']
        sequence = 10

        for cust in structure['customers']:
            pid = cust['partner_id']
            sid = cust['salesperson_id']

            invoices = [inv for inv in cust['invoices'] if inv['type'] == 'invoice']
            invoices.sort(key=lambda inv: (inv.get('invoice_date') or date.min, inv.get('move_id') or 0))

            for inv in invoices:
                parent = line_obj.create({
                    'report_id': report.id,
                    'company_id': company.id,
                    'partner_id': pid,
                    'salesperson_id': sid,
                    'date': inv['invoice_date'],
                    'date_due': inv['date_due'],
                    'entry_type': 'invoice',
                    'move_id': inv['move_id'],
                    'journal_id': inv['journal_id'],
                    'document': inv['document_name'],
                    'reference': inv['reference'],
                    'currency_id': inv['currency_id'],
                    'amount_total': inv['amount_total'],
                    'amount_applied': inv['amount_applied'],
                    'residual': inv['amount_residual'],
                    'amount_pending_draft': 0.0,
                    'legend': '',
                    'bucket_aging': inv['bucket'] if inv['bucket'] != 'na' else 'na',
                    'bucket_0_30': inv['bucket_0_30'],
                    'bucket_31_60': inv['bucket_31_60'],
                    'bucket_61_90': inv['bucket_61_90'],
                    'bucket_91_plus': inv['bucket_91_plus'],
                    'payment_state': inv['payment_state'],
                    'level': 0,
                    'sequence': sequence,
                })
                sequence += 1

                for applied in inv.get('applied_lines', []):
                    kind = applied.get('counterpart_kind')
                    if kind == 'payment':
                        child_type = 'payment_applied'
                        legend = _('Pago aplicado')
                        default_doc = _('Pago')
                    elif kind == 'credit_note':
                        child_type = 'credit_note'
                        legend = _('NC aplicada')
                        default_doc = _('Nota de crédito')
                    else:
                        child_type = 'credit_note'
                        legend = _('Reversión aplicada')
                        default_doc = _('Reversión')

                    line_obj.create({
                        'report_id': report.id,
                        'company_id': company.id,
                        'partner_id': pid,
                        'salesperson_id': sid,
                        'parent_id': parent.id,
                        'level': 1,
                        'sequence': sequence,
                        'date': applied.get('counterpart_date'),
                        'date_due': None,
                        'entry_type': child_type,
                        'move_id': applied.get('counterpart_move_id') or False,
                        'payment_id': applied.get('counterpart_payment_id') or False,
                        'journal_id': applied.get('counterpart_journal_id') or False,
                        'document': applied.get('counterpart_name') or default_doc,
                        'reference': applied.get('counterpart_reference') or '',
                        'currency_id': applied.get('counterpart_currency_id') or inv['currency_id'],
                        'amount_total': 0.0,
                        'amount_applied': applied.get('applied_amount') or 0.0,
                        'residual': 0.0,
                        'amount_pending_draft': 0.0,
                        'legend': legend,
                        'bucket_aging': 'na',
                        'bucket_0_30': 0.0,
                        'bucket_31_60': 0.0,
                        'bucket_61_90': 0.0,
                        'bucket_91_plus': 0.0,
                        'payment_state': applied.get('counterpart_payment_state') or '',
                    })
                    sequence += 1

            if self.show_draft_payments:
                for dp in cust['draft_payments']:
                    line_obj.create({
                        'report_id': report.id,
                        'company_id': company.id,
                        'partner_id': pid,
                        'salesperson_id': sid,
                        'date': dp.get('payment_date'),
                        'date_due': None,
                        'entry_type': 'payment_draft',
                        'move_id': False,
                        'payment_id': dp['payment_id'],
                        'journal_id': dp['journal_id'],
                        'document': dp.get('payment_name') or '',
                        'reference': dp.get('reference') or '',
                        'currency_id': dp['currency_id'],
                        'amount_total': 0.0,
                        'amount_applied': 0.0,
                        'residual': 0.0,
                        'amount_pending_draft': dp['amount'],
                        'legend': _('Pendiente por aplicar'),
                        'bucket_aging': 'na',
                        'bucket_0_30': 0.0,
                        'bucket_31_60': 0.0,
                        'bucket_61_90': 0.0,
                        'bucket_91_plus': 0.0,
                        'payment_state': 'draft',
                        'level': 0,
                        'sequence': sequence,
                    })
                    sequence += 1

    # ======================================================================
    # ACCIÓN 2: PDF (QWeb)
    # ======================================================================
    def _get_report_data(self):
        """Construye el dict serializable para PDF y XLSX."""
        structure = self._compute_report_structure()
        return {
            'wizard_id': self.id,
            'date_from': self._format_date_dmy(self.date_from),
            'date_to': self._format_date_dmy(self.date_to),
            'report_mode': self.report_mode,
            'show_draft_payments': self.show_draft_payments,
            'include_credit_notes': self.include_credit_notes,
            'currency_display': self.currency_display,
            'company': self.env.company,
            'customers': structure['customers'],
            'grand_totals': structure['grand_totals'],
        }

    def action_print_pdf(self):
        """Genera y descarga el reporte PDF (QWeb)."""
        self.ensure_one()
        report_mode_ctx = self.env.context.get('report_mode_ctx')
        if report_mode_ctx in ('summary', 'detail') and self.report_mode != report_mode_ctx:
            # Asegura coherencia con el modo seleccionado en el formulario.
            self.write({'report_mode': report_mode_ctx})
        # Se envía solo wizard_id (payload pequeño) y el parser recalcula datos.
        # Evita URLs enormes en /report/download y mantiene filtros consistentes.
        return self.env.ref(
            'sng_customer_statement.action_report_customer_statement'
        ).report_action(self, data={'wizard_id': self.id})

    # ======================================================================
    # ACCIÓN 3: XLSX
    # ======================================================================
    def action_print_excel(self):
        """Genera y descarga el reporte XLSX."""
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_(
                "La librería Python 'xlsxwriter' es necesaria. "
                "Instálela con: pip install xlsxwriter"
            ))
        report_mode_ctx = self.env.context.get('report_mode_ctx')
        if report_mode_ctx in ('summary', 'detail') and self.report_mode != report_mode_ctx:
            # Asegura que el backend use el modo seleccionado en el formulario.
            self.write({'report_mode': report_mode_ctx})
        data = self._get_report_data()
        output = self._build_excel(data)
        filename = f"estado_cuenta_{self.report_mode}_{self.date_from}_{self.date_to}.xlsx"
        self.write({
            'excel_file': base64.b64encode(output.getvalue()),
            'excel_filename': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': (
                f'/web/content/{self._name}/{self.id}'
                f'/excel_file/{filename}?download=true'
            ),
            'target': 'new',
        }

    # ======================================================================
    # GENERADOR XLSX (sin cambios funcionales)
    # ======================================================================
    def _build_excel(self, data):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        fmt_title    = wb.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        fmt_subtitle = wb.add_format({'font_size': 10, 'align': 'center', 'italic': True})
        fmt_header   = wb.add_format({
            'bold': True, 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#2E75B6', 'font_color': 'white', 'border': 1, 'text_wrap': True,
        })
        fmt_partner  = wb.add_format({'bold': True, 'font_size': 10, 'bg_color': '#D6E4F0', 'border': 1})
        fmt_cell     = wb.add_format({'font_size': 9, 'align': 'left', 'border': 1})
        fmt_num      = wb.add_format({'font_size': 9, 'align': 'right', 'num_format': '#,##0.00', 'border': 1})
        fmt_num_blue = wb.add_format({'font_size': 9, 'align': 'right', 'num_format': '#,##0.00', 'border': 1, 'font_color': '#1F618D'})
        fmt_num_red  = wb.add_format({'font_size': 9, 'align': 'right', 'num_format': '#,##0.00', 'border': 1, 'font_color': '#C0392B'})
        fmt_draft    = wb.add_format({'font_size': 9, 'align': 'left', 'border': 1, 'font_color': '#7F8C8D', 'italic': True})
        fmt_draftnum = wb.add_format({'font_size': 9, 'align': 'right', 'num_format': '#,##0.00', 'border': 1, 'font_color': '#7F8C8D', 'italic': True})
        fmt_total    = wb.add_format({'bold': True, 'font_size': 10, 'align': 'right', 'num_format': '#,##0.00', 'bg_color': '#FFF2CC', 'border': 2})
        fmt_totlbl   = wb.add_format({'bold': True, 'font_size': 10, 'bg_color': '#FFF2CC', 'border': 2})
        fmt_warn     = wb.add_format({'font_size': 9, 'italic': True, 'font_color': '#E67E22', 'border': 1})

        company = data['company']
        if data['report_mode'] == 'summary':
            self._write_excel_summary(wb, data, company, fmt_title, fmt_subtitle, fmt_header,
                                      fmt_partner, fmt_cell, fmt_num, fmt_num_blue, fmt_num_red,
                                      fmt_draftnum, fmt_total, fmt_totlbl)
        else:
            for cust in data['customers']:
                self._write_excel_detail_sheet(wb, cust, data, company, fmt_title, fmt_header,
                                               fmt_partner, fmt_cell, fmt_num, fmt_num_red,
                                               fmt_num_blue, fmt_draft, fmt_draftnum, fmt_warn,
                                               fmt_total, fmt_totlbl)
        wb.close()
        output.seek(0)
        return output

    def _write_excel_summary(self, wb, data, company,
                              fmt_title, fmt_subtitle, fmt_header, fmt_partner,
                              fmt_cell, fmt_num, fmt_num_blue, fmt_num_red,
                              fmt_draft_num, fmt_total, fmt_total_lbl):
        ws = wb.add_worksheet('Resumen')
        ws.set_column('A:A', 35); ws.set_column('B:B', 14); ws.set_column('C:C', 15)
        ws.set_column('D:D', 15); ws.set_column('E:E', 15); ws.set_column('F:F', 15)
        ws.set_column('G:G', 11); ws.set_column('H:H', 11); ws.set_column('I:I', 11)
        ws.set_column('J:J', 11); ws.set_column('K:K', 12); ws.set_column('L:L', 12)
        row = 0
        ws.merge_range(row, 0, row, 11, f"ESTADO DE CUENTA DE CLIENTES — {company.name}", fmt_title); row += 1
        ws.merge_range(row, 0, row, 11, f"Período: {data['date_from']} al {data['date_to']}", fmt_subtitle); row += 2
        headers = ['Cliente','RUC/NIT','Total Facturado','Total Pagado','Saldo Pendiente',
                   'Pendiente x Aplicar','Venc. 0-30','Venc. 31-60','Venc. 61-90','Venc. 91+',
                   'Últ. Factura','Últ. Pago']
        for col, h in enumerate(headers):
            ws.write(row, col, h, fmt_header)
        row += 1
        for cust in data['customers']:
            ws.write(row, 0, self._coerce_translated_text(cust['partner_name']), fmt_partner)
            ws.write(row, 1, cust['partner_vat'], fmt_cell)
            ws.write(row, 2, cust['total_invoiced'], fmt_num)
            ws.write(row, 3, cust['total_applied'], fmt_num_blue)
            ws.write(row, 4, cust['total_residual'], fmt_num_red if cust['total_residual'] > 0 else fmt_num)
            ws.write(row, 5, cust['total_draft_pending'], fmt_draft_num)
            ws.write(row, 6, cust['bucket_0_30'], fmt_num)
            ws.write(row, 7, cust['bucket_31_60'], fmt_num)
            ws.write(row, 8, cust['bucket_61_90'], fmt_num)
            ws.write(row, 9, cust['bucket_91_plus'], fmt_num_red if cust['bucket_91_plus'] > 0 else fmt_num)
            ws.write(row, 10, self._format_date_dmy(cust.get('last_invoice_date')), fmt_cell)
            ws.write(row, 11, self._format_date_dmy(cust.get('last_payment_date')), fmt_cell)
            row += 1
        gt = data['grand_totals']
        row += 1
        ws.merge_range(row, 0, row, 1, 'TOTAL GENERAL', fmt_total_lbl)
        for col, key in enumerate(['total_invoiced','total_applied','total_residual',
                                    'total_draft_pending','bucket_0_30','bucket_31_60',
                                    'bucket_61_90','bucket_91_plus'], start=2):
            ws.write(row, col, gt[key], fmt_total)
        ws.write(row, 10, '', fmt_total); ws.write(row, 11, '', fmt_total)

    def _write_excel_detail_sheet(self, wb, cust, data, company,
                                   fmt_title, fmt_header, fmt_partner,
                                   fmt_cell, fmt_num, fmt_num_red, fmt_num_blue,
                                   fmt_draft, fmt_draft_num, fmt_warn,
                                   fmt_total, fmt_total_lbl):
        partner_name = self._coerce_translated_text(cust['partner_name']) or ''
        sheet_name = partner_name[:28].replace('/', '-').replace('\\', '-')
        ws = wb.add_worksheet(sheet_name)
        ws.set_column('A:A', 12); ws.set_column('B:B', 16); ws.set_column('C:C', 24)
        ws.set_column('D:D', 18); ws.set_column('E:E', 20); ws.set_column('F:F', 12)
        ws.set_column('G:G', 14); ws.set_column('H:H', 14); ws.set_column('I:I', 14)
        ws.set_column('J:J', 16)
        row = 0
        ws.merge_range(row, 0, row, 9, f"Estado de Cuenta — {partner_name}", fmt_title); row += 1
        ws.merge_range(row, 0, row, 9,
                       f"{company.name}  |  Período: {data['date_from']} al {data['date_to']}",
                       wb.add_format({'align': 'center', 'font_size': 9, 'italic': True})); row += 2
        for col, h in enumerate(['Fecha','Tipo','Documento','Diario','Referencia','Moneda',
                                 'Monto','Aplicado','Saldo','Estado']):
            ws.write(row, col, h, fmt_header)
        row += 1

        invoices = [inv for inv in cust['invoices'] if inv['type'] == 'invoice']
        invoices.sort(key=lambda inv: (inv.get('invoice_date') or date.min, inv.get('move_id') or 0))

        subtotal_invoiced = 0.0
        subtotal_applied = 0.0
        subtotal_residual = 0.0

        for inv in invoices:
            ws.write(row, 0, self._format_date_dmy(inv.get('invoice_date')), fmt_cell)
            ws.write(row, 1, 'Factura', fmt_cell)
            ws.write(row, 2, self._coerce_translated_text(inv['document_name']), fmt_partner)
            ws.write(row, 3, self._coerce_translated_text(inv['journal_name']), fmt_cell)
            ws.write(row, 4, self._coerce_translated_text(inv['reference']) or '', fmt_cell)
            ws.write(row, 5, self._coerce_translated_text(inv['currency_name']), fmt_cell)
            ws.write(row, 6, inv['amount_total'], fmt_num)
            ws.write(row, 7, inv['amount_applied'], fmt_num_blue)
            ws.write(row, 8, inv['amount_residual'], fmt_num_red if inv['amount_residual'] > 0 else fmt_num)
            ws.write(row, 9, self._coerce_translated_text(inv['payment_state']), fmt_cell)
            row += 1

            subtotal_invoiced += inv['amount_total']
            subtotal_applied += inv['amount_applied']
            subtotal_residual += inv['amount_residual']

            for ap in inv.get('applied_lines', []):
                kind = ap.get('counterpart_kind')
                if kind == 'payment':
                    type_label = 'Pago aplicado'
                elif kind == 'credit_note':
                    type_label = 'NC aplicada'
                else:
                    type_label = 'Reversion aplicada'

                ws.write(row, 0, self._format_date_dmy(ap.get('counterpart_date')), fmt_draft)
                ws.write(row, 1, type_label, fmt_draft)
                ws.write(row, 2, '   -> ' + (self._coerce_translated_text(ap.get('counterpart_name')) or ''), fmt_draft)
                ws.write(row, 3, self._coerce_translated_text(ap.get('counterpart_journal_name')), fmt_draft)
                ws.write(row, 4, self._coerce_translated_text(ap.get('counterpart_reference')) or '', fmt_draft)
                ws.write(row, 5, self._coerce_translated_text(ap.get('counterpart_currency_name')), fmt_draft)
                ws.write(row, 6, 0.0, fmt_draft_num)
                ws.write(row, 7, ap.get('applied_amount') or 0.0, fmt_draft_num)
                ws.write(row, 8, 0.0, fmt_draft_num)
                ws.write(row, 9, self._coerce_translated_text(ap.get('counterpart_payment_state')) or '', fmt_draft)
                row += 1

        if data['show_draft_payments'] and cust['draft_payments']:
            row += 1
            ws.merge_range(row, 0, row, 9,
                           '⚠ PAGOS EN BORRADOR — Pendiente por aplicar (no afectan saldo)', fmt_warn); row += 1
            for dp in cust['draft_payments']:
                ws.write(row, 0, self._format_date_dmy(dp.get('payment_date')), fmt_draft)
                ws.write(row, 1, 'Pago borrador', fmt_draft)
                ws.write(row, 2, self._coerce_translated_text(dp.get('payment_name')) or '', fmt_draft)
                ws.write(row, 3, self._coerce_translated_text(dp.get('journal_name', '')), fmt_draft)
                ws.write(row, 4, self._coerce_translated_text(dp.get('reference')) or '', fmt_draft)
                ws.write(row, 5, self._coerce_translated_text(dp.get('currency_name', '')), fmt_draft)
                ws.write(row, 6, dp['amount'], fmt_draft_num)
                ws.write(row, 7, 0.0, fmt_draft_num)
                ws.write(row, 8, 0.0, fmt_draft_num)
                ws.write(row, 9, 'Pendiente por aplicar', fmt_draft)
                row += 1
        row += 1
        ws.merge_range(row, 0, row, 5, f'Subtotal — {partner_name}', fmt_total_lbl)
        ws.write(row, 6, subtotal_invoiced, fmt_total)
        ws.write(row, 7, subtotal_applied, fmt_total)
        ws.write(row, 8, subtotal_residual, fmt_total)
        ws.write(row, 9, '', fmt_total)
