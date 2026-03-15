# -*- coding: utf-8 -*-
"""
Modelos persistentes para el reporte "Estado de Cuenta de Clientes".

CustomerStatementReport (cabecera)
    └── CustomerStatementReportLine (líneas detalle/resumen)

Filosofía de diseño:
- Los registros se crean desde el wizard y son persistentes (no transient).
- El usuario puede volver a consultarlos desde el menú "Estados Generados".
- Record rules aseguran que cada usuario solo ve sus propios reportes
  o los de su empresa (configurable).
- Las líneas son la unidad atómica: una por factura, una por pago aplicado
  y una por pago draft. Esto permite usar filtros/group_by nativos de Odoo.
"""

from odoo import api, fields, models


# ── Selecciones reutilizables ────────────────────────────────────────────────
ENTRY_TYPE_SELECTION = [
    ('invoice',          'Factura'),
    ('credit_note',      'Nota de Crédito'),
    ('payment_applied',  'Pago Aplicado'),
    ('payment_draft',    'Pago en Borrador'),   # Informativo — no afecta saldo
]

AGING_SELECTION = [
    ('current',    'Al día'),
    ('0_30',       '0-30 días'),
    ('31_60',      '31-60 días'),
    ('61_90',      '61-90 días'),
    ('91_plus',    '91+ días'),
    ('na',         'N/A'),               # Para pagos, NC, etc.
]

MODE_SELECTION = [
    ('summary', 'Resumen por cliente'),
    ('detail',  'Detalle por cliente'),
]

CURRENCY_MODE_SELECTION = [
    ('company', 'Moneda de la empresa'),
    ('invoice', 'Moneda de la factura'),
]


# ── Modelo Cabecera ──────────────────────────────────────────────────────────
class CustomerStatementReport(models.Model):
    _name = 'customer.statement.report'
    _description = 'Cabecera: Estado de Cuenta de Clientes'
    _order = 'create_date desc'
    # Limpiar registros con más de 24 h de antigüedad en GC de transient
    # (no son transient, pero se limpian manualmente o via ir.cron si se desea)

    name = fields.Char(
        string='Nombre',
        required=True,
        default=lambda self: self._default_name(),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string='Fecha Desde', required=True)
    date_to = fields.Date(string='Fecha Hasta', required=True)

    # Filtros aplicados (guardados para referencia futura)
    partner_ids = fields.Many2many(
        'res.partner',
        'csr_partner_rel',
        'report_id', 'partner_id',
        string='Clientes filtrados',
    )
    salesperson_ids = fields.Many2many(
        'res.partner',
        'csr_salesperson_rel',
        'report_id', 'partner_id',
        string='Vendedores filtrados',
        domain="[('is_salesperson', '=', True)]",
    )
    tag_ids = fields.Many2many(
        'res.partner.category',
        'csr_tag_rel',
        'report_id', 'tag_id',
        string='Etiquetas filtradas',
    )

    # Opciones del reporte
    mode = fields.Selection(MODE_SELECTION, string='Modo', required=True, default='summary')
    currency_mode = fields.Selection(CURRENCY_MODE_SELECTION, string='Modo moneda', default='company')
    include_credit_notes = fields.Boolean(string='Incluye NC', default=True)
    show_draft_payments = fields.Boolean(string='Muestra pagos borrador', default=True)
    only_with_balance = fields.Boolean(string='Solo con saldo', default=False)

    # Líneas generadas
    line_ids = fields.One2many(
        'customer.statement.report.line',
        'report_id',
        string='Líneas',
    )
    line_count = fields.Integer(
        string='# Líneas',
        compute='_compute_line_count',
    )

    # Totales calculados (campo store=False, se calcula en pantalla vía líneas)
    total_invoiced = fields.Float(
        string='Total Facturado',
        compute='_compute_totals',
    )
    total_applied = fields.Float(
        string='Total Pagado',
        compute='_compute_totals',
    )
    total_residual = fields.Float(
        string='Saldo Pendiente',
        compute='_compute_totals',
    )
    total_draft_pending = fields.Float(
        string='Pendiente por Aplicar',
        compute='_compute_totals',
    )

    @api.model
    def _default_name(self):
        from datetime import datetime
        return f"Estado Cuenta {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('line_ids.amount_total', 'line_ids.amount_applied',
                 'line_ids.residual', 'line_ids.amount_pending_draft',
                 'line_ids.entry_type', 'line_ids.level')
    def _compute_totals(self):
        for rec in self:
            inv_lines = rec.line_ids.filtered(
                lambda l: l.level == 0 and l.entry_type in ('invoice', 'credit_note')
            )
            rec.total_invoiced = sum(inv_lines.mapped('amount_total'))
            rec.total_applied = sum(inv_lines.mapped('amount_applied'))
            rec.total_residual = sum(inv_lines.mapped('residual'))
            draft_lines = rec.line_ids.filtered(
                lambda l: l.level == 0 and l.entry_type == 'payment_draft'
            )
            rec.total_draft_pending = sum(draft_lines.mapped('amount_pending_draft'))

    def action_view_lines(self):
        """Smart button: abre vista tree de líneas filtradas por este reporte."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Líneas — {self.name}',
            'res_model': 'customer.statement.report.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id,
                'group_by': ['partner_id'],
            },
        }


# ── Modelo Líneas ────────────────────────────────────────────────────────────
class CustomerStatementReportLine(models.Model):
    _name = 'customer.statement.report.line'
    _description = 'Línea: Estado de Cuenta de Clientes'
    _order = 'partner_id, sequence, id'

    report_id = fields.Many2one(
        'customer.statement.report',
        string='Reporte',
        required=True,
        ondelete='cascade',   # Al borrar cabecera se borran líneas
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Quién ───────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        index=True,
    )
    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        domain="[('is_salesperson', '=', True)]",
        index=True,
    )
    parent_id = fields.Many2one(
        'customer.statement.report.line',
        string='Línea Padre',
        index=True,
        ondelete='cascade',
    )
    child_ids = fields.One2many(
        'customer.statement.report.line',
        'parent_id',
        string='Líneas Hija',
    )
    level = fields.Integer(
        string='Nivel',
        default=0,
        index=True,
        help='0 = línea padre (factura/draft), 1 = línea hija (aplicación).',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        index=True,
        help='Controla el orden: primero factura padre, luego sus hijos.',
    )

    # ── Cuándo ──────────────────────────────────────────────────────────────
    date = fields.Date(string='Fecha', index=True)
    date_due = fields.Date(string='Fecha Vencimiento')

    # ── Qué ─────────────────────────────────────────────────────────────────
    entry_type = fields.Selection(
        ENTRY_TYPE_SELECTION,
        string='Tipo',
        required=True,
        index=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Asiento',
        ondelete='set null',
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
        ondelete='set null',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
    )

    # Nombre / referencia visible en la vista
    document = fields.Char(string='Documento')
    display_document = fields.Char(
        string='Documento',
        compute='_compute_display_document',
        store=True,
    )
    reference = fields.Char(string='Referencia')

    # ── Importes ─────────────────────────────────────────────────────────────
    currency_id = fields.Many2one('res.currency', string='Moneda')

    # amount_total: monto de la factura (signo negativo para NC)
    # amount_applied: lo que se concilió (pagos aplicados a esta factura)
    # residual: saldo pendiente (amount_total - amount_applied para facturas)
    # amount_pending_draft: monto del pago en borrador (solo si entry_type=payment_draft)
    amount_total = fields.Float(
        string='Monto',
        digits='Account',
        help="Monto total del documento. Negativo para notas de crédito.",
    )
    amount_applied = fields.Float(
        string='Pagado/Aplicado',
        digits='Account',
        help="Total conciliado/aplicado contra esta factura. "
             "CERO para pagos draft (no afectan saldo contable).",
    )
    residual = fields.Float(
        string='Saldo',
        digits='Account',
        help="Saldo pendiente = amount_total - amount_applied. "
             "Para pagos aplicados y drafts es 0.",
    )
    amount_pending_draft = fields.Float(
        string='Pendiente por Aplicar',
        digits='Account',
        help="Monto del pago en borrador (solo informativo). "
             "NO se suma al aplicado ni afecta el saldo contable.",
    )

    # ── Clasificación aging ──────────────────────────────────────────────────
    bucket_aging = fields.Selection(
        AGING_SELECTION,
        string='Antigüedad',
        default='na',
        index=True,
    )

    # ── Leyenda visual ───────────────────────────────────────────────────────
    legend = fields.Char(
        string='Leyenda',
        help="'Pendiente por aplicar' para pagos en borrador. Vacío para el resto.",
    )

    # ── Estado del documento ─────────────────────────────────────────────────
    payment_state = fields.Char(string='Estado de Pago')

    # ── Campos de agrupación para pivot/graph ────────────────────────────────
    # Campos monetarios opcionales para pivot (Odoo los pide como Float para agrupar)
    bucket_0_30 = fields.Float(
        string='Venc. 0-30',
        digits='Account',
        help="Saldo en bucket 0-30 días vencido.",
    )
    bucket_31_60 = fields.Float(
        string='Venc. 31-60',
        digits='Account',
    )
    bucket_61_90 = fields.Float(
        string='Venc. 61-90',
        digits='Account',
    )
    bucket_91_plus = fields.Float(
        string='Venc. 91+',
        digits='Account',
    )

    @api.depends('document', 'level')
    def _compute_display_document(self):
        for rec in self:
            base = rec.document or ''
            rec.display_document = f"{'   ' * max(rec.level, 0)}{base}"
