# -*- coding: utf-8 -*-

import base64
from datetime import date
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import xlsxwriter


class SngCommercialPlan(models.Model):
    _name = 'sng.commercial.plan'
    _description = 'SNG Commercial Plan'
    _order = 'target_year desc, id desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        copy=False,
        default=lambda self: self._default_name(),
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Moneda',
        store=True,
        readonly=True,
    )
    base_year = fields.Integer(
        string='Ano Base',
        required=True,
        default=lambda self: fields.Date.today().year - 1,
    )
    target_year = fields.Integer(
        string='Ano Objetivo',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    budget_total = fields.Monetary(string='Presupuesto Total')
    target_total_manual = fields.Monetary(
        string='Meta Total Manual',
        help='Si se define, se usa como meta protegida total para calcular el factor real del plan.',
    )
    use_global_factor = fields.Boolean(
        string='Usar Factor Global',
        default=True,
    )
    global_growth_factor = fields.Float(
        string='Factor Global',
        default=1.0,
        digits=(16, 4),
    )
    growth_factor_a = fields.Float(
        string='Factor Segmento A',
        default=1.0,
        digits=(16, 4),
    )
    growth_factor_b = fields.Float(
        string='Factor Segmento B',
        default=1.0,
        digits=(16, 4),
    )
    growth_factor_c = fields.Float(
        string='Factor Segmento C',
        default=1.0,
        digits=(16, 4),
    )
    a_limit_percent = fields.Float(
        string='Limite Segmento A',
        default=0.70,
        digits=(16, 4),
    )
    b_limit_percent = fields.Float(
        string='Limite Segmento B',
        default=0.90,
        digits=(16, 4),
    )
    dpp_limit_a = fields.Integer(
        string='Limite DPP A',
        default=30,
    )
    dpp_limit_b = fields.Integer(
        string='Limite DPP B',
        default=45,
    )
    empty_dpp_label = fields.Char(
        string='Etiqueta Sin DPP',
        default='Sin DPP',
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('calculated', 'Calculado'),
            ('closed', 'Cerrado'),
        ],
        string='Estado',
        default='draft',
        required=True,
        tracking=False,
        index=True,
    )
    line_ids = fields.One2many(
        'sng.commercial.plan.line',
        'plan_id',
        string='Lineas',
    )
    total_base_sales = fields.Monetary(
        string='Venta Base Total',
        compute='_compute_totals',
        store=True,
    )
    total_target_sales = fields.Monetary(
        string='Meta Total',
        compute='_compute_totals',
        store=True,
    )
    total_current_sales = fields.Monetary(
        string='Venta Actual Total',
        compute='_compute_totals',
        store=True,
    )
    protected_target_total = fields.Monetary(
        string='Meta Protegida Total',
        compute='_compute_target_parameters',
        store=True,
    )
    effective_growth_factor = fields.Float(
        string='Factor Crecimiento Real',
        compute='_compute_target_parameters',
        store=True,
        digits=(16, 6),
    )
    total_compliance_percent = fields.Float(
        string='Cumplimiento General',
        compute='_compute_totals',
        store=True,
        digits=(16, 4),
    )
    segment_a_count = fields.Integer(
        string='Clientes Segmento A',
        compute='_compute_segment_counts',
        store=True,
    )
    segment_b_count = fields.Integer(
        string='Clientes Segmento B',
        compute='_compute_segment_counts',
        store=True,
    )
    segment_c_count = fields.Integer(
        string='Clientes Segmento C',
        compute='_compute_segment_counts',
        store=True,
    )
    no_dpp_count = fields.Integer(
        string='Clientes Sin DPP',
        compute='_compute_segment_counts',
        store=True,
    )
    line_count = fields.Integer(
        string='Clientes',
        compute='_compute_segment_counts',
        store=True,
    )

    @api.model
    def _default_name(self):
        current_year = fields.Date.today().year
        return _('Plan Comercial %s') % current_year

    @api.depends(
        'line_ids',
        'line_ids.base_sales_amount',
        'line_ids.target_amount',
        'line_ids.current_sales_amount',
    )
    def _compute_totals(self):
        for plan in self:
            total_base = sum(plan.line_ids.mapped('base_sales_amount'))
            total_target = sum(plan.line_ids.mapped('target_amount'))
            total_current = sum(plan.line_ids.mapped('current_sales_amount'))
            plan.total_base_sales = total_base
            plan.total_target_sales = total_target
            plan.total_current_sales = total_current
            plan.total_compliance_percent = total_current / total_target if total_target else 0.0

    @api.depends(
        'budget_total',
        'global_growth_factor',
        'line_ids.target_amount',
        'target_total_manual',
        'total_base_sales',
        'total_target_sales',
        'use_global_factor',
    )
    def _compute_target_parameters(self):
        for plan in self:
            effective_factor = plan._get_effective_growth_factor(plan.total_base_sales)
            if plan.use_global_factor:
                protected_total = (
                    plan.target_total_manual
                    or plan.budget_total
                    or (plan.total_base_sales * effective_factor)
                )
            else:
                protected_total = plan.total_target_sales

            plan.protected_target_total = protected_total
            plan.effective_growth_factor = effective_factor

    @api.depends('line_ids', 'line_ids.sales_segment', 'line_ids.dpp_segment')
    def _compute_segment_counts(self):
        for plan in self:
            plan.segment_a_count = len(plan.line_ids.filtered(lambda line: line.sales_segment == 'a'))
            plan.segment_b_count = len(plan.line_ids.filtered(lambda line: line.sales_segment == 'b'))
            plan.segment_c_count = len(plan.line_ids.filtered(lambda line: line.sales_segment == 'c'))
            plan.no_dpp_count = len(plan.line_ids.filtered(lambda line: line.dpp_segment == 'no_dpp'))
            plan.line_count = len(plan.line_ids)

    @api.constrains('base_year', 'target_year')
    def _check_years(self):
        for plan in self:
            if plan.base_year <= 0 or plan.target_year <= 0:
                raise ValidationError(_('Los anos deben ser mayores a cero.'))

    @api.constrains('a_limit_percent', 'b_limit_percent')
    def _check_segment_limits(self):
        for plan in self:
            if not 0 < plan.a_limit_percent <= 1:
                raise ValidationError(_('El limite del segmento A debe estar entre 0 y 1.'))
            if not 0 < plan.b_limit_percent <= 1:
                raise ValidationError(_('El limite del segmento B debe estar entre 0 y 1.'))
            if plan.a_limit_percent >= plan.b_limit_percent:
                raise ValidationError(_('El limite del segmento B debe ser mayor que el limite del segmento A.'))

    @api.constrains('dpp_limit_a', 'dpp_limit_b')
    def _check_dpp_limits(self):
        for plan in self:
            if plan.dpp_limit_a < 0 or plan.dpp_limit_b < 0:
                raise ValidationError(_('Los limites DPP no pueden ser negativos.'))
            if plan.dpp_limit_a > plan.dpp_limit_b:
                raise ValidationError(_('El limite DPP A no puede ser mayor que el limite DPP B.'))

    def action_load_customers(self):
        self.ensure_one()
        self._check_plan_is_editable()
        sales_map = {
            partner_id: amount
            for partner_id, amount in self._get_sales_by_partner(self.base_year).items()
            if amount > 0
        }
        partner_ids = set(sales_map.keys())
        existing_lines = self.line_ids
        existing_partner_ids = set(existing_lines.mapped('partner_id').ids)

        lines_to_remove = existing_lines.filtered(lambda line: line.partner_id.id not in partner_ids)
        if lines_to_remove:
            lines_to_remove.unlink()

        partner_model = self.env['res.partner']
        create_vals_list = []
        for partner_id in sorted(partner_ids - existing_partner_ids):
            partner = partner_model.browse(partner_id).commercial_partner_id
            create_vals_list.append({
                'plan_id': self.id,
                'partner_id': partner.id,
                **self.env['sng.commercial.plan.line']._prepare_partner_snapshot_vals(partner),
            })

        if create_vals_list:
            self.env['sng.commercial.plan.line'].create(create_vals_list)

        return self._display_notification(
            _('Se sincronizaron %s clientes con ventas en el ano base.') % len(partner_ids)
        )

    def action_calculate_plan(self):
        self.ensure_one()
        self._check_plan_is_editable()
        if not self.line_ids:
            self.action_load_customers()
        self._recalculate_plan_lines()
        self.state = 'calculated'
        return self._display_notification(_('El plan comercial fue calculado correctamente.'))

    def action_recalculate_metrics(self):
        self.ensure_one()
        self._check_plan_is_editable()
        if not self.line_ids:
            raise UserError(_('Primero debe cargar las lineas del plan.'))
        self._recalculate_plan_lines()
        if self.state == 'draft':
            self.state = 'calculated'
        return self._display_notification(_('Las metricas del plan fueron recalculadas.'))

    def action_set_draft(self):
        self.ensure_one()
        self.state = 'draft'
        return self._display_notification(_('El plan se regreso a borrador.'))

    def action_close(self):
        self.ensure_one()
        self.state = 'closed'
        return self._display_notification(_('El plan fue cerrado.'))

    def action_open_export_wizard(self):
        self.ensure_one()
        wizard = self.env['sng.commercial.plan.export.wizard'].create({
            'plan_id': self.id,
        })
        return wizard.action_generate_file()

    def _check_plan_is_editable(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_('No se puede modificar un plan cerrado.'))

    def _display_notification(self, message, notif_type='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Plan Comercial'),
                'message': message,
                'type': notif_type,
                'sticky': False,
            },
        }

    def _recalculate_plan_lines(self):
        self.ensure_one()
        partner_ids = self.line_ids.mapped('partner_id').ids
        base_sales_map = self._get_sales_by_partner(self.base_year, partner_ids=partner_ids)
        current_sales_map = self._get_sales_by_partner(
            self.target_year,
            partner_ids=partner_ids,
            year_to_date=True,
        )
        dpp_map = self._get_dpp_by_partner(partner_ids=partner_ids)
        elapsed_months = self._get_elapsed_months()

        lines_ordered = self.line_ids.sorted(
            key=lambda line: (
                -base_sales_map.get(line.partner_id.id, 0.0),
                (line.partner_id.display_name or '').lower(),
                line.id,
            )
        )
        total_base_sales = sum(base_sales_map.get(line.partner_id.id, 0.0) for line in lines_ordered)
        effective_growth_factor = self._get_effective_growth_factor(total_base_sales)
        cumulative_percent = 0.0

        for sequence, line in enumerate(lines_ordered, start=1):
            partner = line.partner_id.commercial_partner_id
            base_sales = base_sales_map.get(partner.id, 0.0)
            current_sales = current_sales_map.get(partner.id, 0.0)
            dpp_value = dpp_map.get(partner.id)
            participation = base_sales / total_base_sales if total_base_sales else 0.0
            cumulative_percent += participation
            sales_segment = self._get_sales_segment(base_sales, cumulative_percent)
            dpp_segment = self._get_dpp_segment(dpp_value)
            target_amount = self._get_target_amount(
                base_sales,
                sales_segment,
                effective_growth_factor=effective_growth_factor,
            )
            monthly_target = target_amount / 12.0 if target_amount else 0.0
            increase_amount = target_amount - base_sales
            average_monthly_sales = current_sales / elapsed_months if elapsed_months else 0.0
            monthly_gap_amount = average_monthly_sales - monthly_target
            projected_sales = average_monthly_sales * 12.0 if elapsed_months else 0.0
            compliance = current_sales / target_amount if target_amount else 0.0
            achievement_gap = compliance - 1.0 if target_amount else 0.0

            line.write({
                **line._prepare_partner_snapshot_vals(partner),
                'segment_order': sequence,
                'base_sales_amount': base_sales,
                'participation_percent': participation,
                'cumulative_percent': cumulative_percent,
                'sales_segment': sales_segment,
                'dpp_value': dpp_value if dpp_value is not None else False,
                'dpp_segment': dpp_segment,
                'final_segment_label': self._get_final_segment_label(sales_segment, dpp_segment),
                'target_amount': target_amount,
                'monthly_target_amount': monthly_target,
                'increase_amount': increase_amount,
                'current_sales_amount': current_sales,
                'average_monthly_sales': average_monthly_sales,
                'monthly_gap_amount': monthly_gap_amount,
                'projected_sales_amount': projected_sales,
                'compliance_percent': compliance,
                'achievement_gap_percent': achievement_gap,
                'budget_amount': line.budget_amount if line.budget_amount not in (False, None) else target_amount,
            })

    def _get_effective_growth_factor(self, total_base_sales=None):
        self.ensure_one()
        total_base_sales = total_base_sales if total_base_sales is not None else self.total_base_sales
        if not self.use_global_factor:
            target_total = self.total_target_sales
            return target_total / total_base_sales if total_base_sales else 0.0

        protected_total = self.target_total_manual or self.budget_total
        if protected_total:
            return protected_total / total_base_sales if total_base_sales else 0.0
        return self.global_growth_factor or 0.0

    def _get_target_amount(self, base_sales_amount, sales_segment, effective_growth_factor=None):
        self.ensure_one()
        if self.use_global_factor:
            if effective_growth_factor is None:
                effective_growth_factor = self._get_effective_growth_factor()
            return base_sales_amount * effective_growth_factor

        factor_map = {
            'a': self.growth_factor_a,
            'b': self.growth_factor_b,
            'c': self.growth_factor_c,
        }
        return base_sales_amount * factor_map.get(sales_segment, 1.0)

    def _get_sales_segment(self, base_sales_amount, cumulative_percent):
        self.ensure_one()
        if base_sales_amount <= 0:
            return 'c'
        if cumulative_percent <= self.a_limit_percent:
            return 'a'
        if cumulative_percent <= self.b_limit_percent:
            return 'b'
        return 'c'

    def _get_dpp_segment(self, dpp_value):
        self.ensure_one()
        if dpp_value is None:
            return 'no_dpp'
        if dpp_value <= self.dpp_limit_a:
            return 'a'
        if dpp_value <= self.dpp_limit_b:
            return 'b'
        return 'c'

    def _get_final_segment_label(self, sales_segment, dpp_segment):
        self.ensure_one()
        sales_label = sales_segment.upper() if sales_segment else 'C'
        if dpp_segment == 'no_dpp':
            return _('Venta %s / %s') % (sales_label, self.empty_dpp_label)
        return _('Venta %s / DPP %s') % (sales_label, dpp_segment.upper())

    def _get_elapsed_months(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.target_year < today.year:
            return 12
        if self.target_year > today.year:
            return 0
        return today.month

    def _get_year_date_range(self, year):
        return date(year, 1, 1), date(year, 12, 31)

    def _get_sales_amount_field(self):
        # El Excel base trabaja mejor con venta neta facturada incluyendo
        # notas de credito dentro del mismo periodo.
        return 'amount_total_signed'

    def _get_sales_by_partner(self, year, partner_ids=None, year_to_date=False):
        self.ensure_one()
        date_from, date_to = self._get_year_date_range(year)
        today = fields.Date.context_today(self)
        if year_to_date:
            if year > today.year:
                return {}
            if year == today.year:
                date_to = today
        field_name = self._get_sales_amount_field()
        query = f"""
            SELECT commercial_partner_id, COALESCE(SUM({field_name}), 0.0) AS amount_total
            FROM account_move
            WHERE move_type IN ('out_invoice', 'out_refund')
              AND state = 'posted'
              AND company_id = %s
              AND COALESCE(invoice_date, date) >= %s
              AND COALESCE(invoice_date, date) <= %s
              AND commercial_partner_id IS NOT NULL
        """
        params = [self.company_id.id, date_from, date_to]
        if partner_ids is not None:
            if not partner_ids:
                return {}
            query += " AND commercial_partner_id = ANY(%s)"
            params.append(partner_ids)
        query += " GROUP BY commercial_partner_id"
        self.env.cr.execute(query, params)
        return {partner_id: amount for partner_id, amount in self.env.cr.fetchall()}

    def _get_dpp_by_partner(self, partner_ids=None):
        self.ensure_one()
        if partner_ids is None:
            partner_ids = self.line_ids.mapped('partner_id').ids
        if not partner_ids:
            return {}
        return self.env['regalarte.customer.metric']._get_dpp_metrics(partner_ids, self.company_id)

    def generate_xlsx_file(self):
        self.ensure_one()
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Plan Comercial'))

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
        })
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
        })
        text_format = workbook.add_format({'border': 1})
        monetary_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00',
        })
        percent_format = workbook.add_format({
            'border': 1,
            'num_format': '0.00%',
        })
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E2F0D9',
            'border': 1,
            'num_format': '#,##0.00',
        })
        total_percent_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E2F0D9',
            'border': 1,
            'num_format': '0.00%',
        })

        factor_format = workbook.add_format({
            'border': 1,
            'num_format': '0.000000',
        })

        headers = [
            _('Codigo'),
            _('Nombre del cliente'),
            _('Agente'),
            _('Venta %s') % self.base_year,
            _('Participacion'),
            _('DPP'),
            _('% Acumulado'),
            _('Segmento Venta + DPP'),
            _('Segmento por venta'),
            _('Meta %s Segmentada (Protegida)') % self.target_year,
            _('Incremento'),
            _('Mensual meta'),
            _('Promedio Mensual'),
            _('Crecimiento'),
            _('Venta Acumulada'),
            _('Cumplimiento'),
            _('Presupuesto %s') % self.target_year,
        ]

        worksheet.merge_range(0, 0, 0, len(headers) - 1, self.name, title_format)
        worksheet.write(1, 0, _('Compania'), header_format)
        worksheet.write(1, 1, self.company_id.display_name, text_format)
        worksheet.write(1, 2, _('Ano Base'), header_format)
        worksheet.write(1, 3, self.base_year, text_format)
        worksheet.write(1, 4, _('Ano Objetivo'), header_format)
        worksheet.write(1, 5, self.target_year, text_format)
        worksheet.write(1, 6, _('Factor Crecimiento Real'), header_format)
        worksheet.write(1, 7, self.effective_growth_factor, factor_format)

        helper_col = len(headers) + 1
        worksheet.write(0, helper_col, _('Total %s') % self.base_year, header_format)
        worksheet.write(0, helper_col + 1, self.total_base_sales, total_format)
        worksheet.write(2, helper_col, _('Meta Protegida %s') % self.target_year, header_format)
        worksheet.write(2, helper_col + 1, self.protected_target_total, total_format)
        worksheet.write(4, helper_col, _('Factor Crecimiento Real'), header_format)
        worksheet.write(4, helper_col + 1, self.effective_growth_factor, factor_format)
        worksheet.write(6, helper_col, _('Validacion Meta Total'), header_format)
        worksheet.write(6, helper_col + 1, self.total_target_sales, total_format)
        worksheet.write(8, helper_col, _('Parametros DPP'), header_format)
        worksheet.write(9, helper_col, _('Limite DPP A'), header_format)
        worksheet.write(9, helper_col + 1, self.dpp_limit_a, text_format)
        worksheet.write(10, helper_col, _('Limite DPP B'), header_format)
        worksheet.write(10, helper_col + 1, self.dpp_limit_b, text_format)
        worksheet.write(11, helper_col, _('Etiqueta sin DPP'), header_format)
        worksheet.write(11, helper_col + 1, self.empty_dpp_label or '', text_format)

        row = 3
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)

        row += 1
        for line in self.line_ids.sorted(key=lambda rec: (rec.segment_order, rec.id)):
            worksheet.write(row, 0, line.customer_code or '', text_format)
            worksheet.write(row, 1, line.commercial_name or line.partner_id.display_name or '', text_format)
            worksheet.write(row, 2, line.assigned_salesperson_id.display_name or '', text_format)
            worksheet.write(row, 3, line.base_sales_amount, monetary_format)
            worksheet.write(row, 4, line.participation_percent, percent_format)
            worksheet.write(row, 5, line.dpp_value if line.dpp_value is not False and line.dpp_value is not None else '', text_format)
            worksheet.write(row, 6, line.cumulative_percent, percent_format)
            worksheet.write(row, 7, line.final_segment_label or '', text_format)
            worksheet.write(row, 8, dict(line._fields['sales_segment'].selection).get(line.sales_segment, '').upper(), text_format)
            worksheet.write(row, 9, line.target_amount, monetary_format)
            worksheet.write(row, 10, line.increase_amount, monetary_format)
            worksheet.write(row, 11, line.monthly_target_amount, monetary_format)
            worksheet.write(row, 12, line.average_monthly_sales, monetary_format)
            worksheet.write(row, 13, line.monthly_gap_amount, monetary_format)
            worksheet.write(row, 14, line.current_sales_amount, monetary_format)
            worksheet.write(row, 15, line.achievement_gap_percent, percent_format)
            worksheet.write(row, 16, line.budget_amount, monetary_format)
            row += 1

        worksheet.write(row, 0, _('Totales'), header_format)
        worksheet.write(row, 3, self.total_base_sales, total_format)
        worksheet.write(row, 4, 1.0 if self.total_base_sales else 0.0, total_percent_format)
        worksheet.write(row, 6, 1.0 if self.total_base_sales else 0.0, total_percent_format)
        worksheet.write(row, 9, self.total_target_sales, total_format)
        worksheet.write(row, 10, sum(self.line_ids.mapped('increase_amount')), total_format)
        worksheet.write(row, 11, sum(self.line_ids.mapped('monthly_target_amount')), total_format)
        worksheet.write(row, 12, sum(self.line_ids.mapped('average_monthly_sales')), total_format)
        worksheet.write(row, 13, sum(self.line_ids.mapped('monthly_gap_amount')), total_format)
        worksheet.write(row, 14, self.total_current_sales, total_format)
        worksheet.write(row, 15, (self.total_current_sales / self.total_target_sales - 1.0) if self.total_target_sales else 0.0, total_percent_format)
        worksheet.write(row, 16, sum(self.line_ids.mapped('budget_amount')), total_format)

        worksheet.freeze_panes(4, 0)
        worksheet.autofilter(3, 0, row, len(headers) - 1)
        worksheet.set_column(0, 2, 24)
        worksheet.set_column(3, 3, 18)
        worksheet.set_column(4, 6, 14)
        worksheet.set_column(7, 8, 20)
        worksheet.set_column(9, 16, 18)
        worksheet.set_column(helper_col, helper_col, 24)
        worksheet.set_column(helper_col + 1, helper_col + 1, 18)

        workbook.close()
        output.seek(0)
        filename = 'plan_comercial_%s_%s.xlsx' % (
            self.target_year,
            self.id,
        )
        return filename, base64.b64encode(output.read())
