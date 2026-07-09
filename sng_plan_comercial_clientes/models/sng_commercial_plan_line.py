# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SngCommercialPlanLine(models.Model):
    _name = 'sng.commercial.plan.line'
    _description = 'SNG Commercial Plan Line'
    _order = 'segment_order asc, base_sales_amount desc, id asc'

    plan_id = fields.Many2one(
        'sng.commercial.plan',
        string='Plan',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        domain=[('customer_rank', '>', 0)],
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='plan_id.company_id',
        string='Compania',
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='plan_id.currency_id',
        string='Moneda',
        store=True,
        readonly=True,
    )
    customer_code = fields.Char(
        string='Codigo Cliente',
        index=True,
    )
    commercial_name = fields.Char(string='Nombre Comercial')
    assigned_salesperson_id = fields.Many2one(
        'res.users',
        string='Vendedor Asignado',
        index=True,
    )
    segment_order = fields.Integer(string='Orden Segmentacion', default=0, index=True)
    base_sales_amount = fields.Monetary(string='Venta Base')
    participation_percent = fields.Float(string='Participacion', digits=(16, 4))
    cumulative_percent = fields.Float(string='Acumulado', digits=(16, 4))
    sales_segment = fields.Selection(
        selection=[
            ('a', 'A'),
            ('b', 'B'),
            ('c', 'C'),
        ],
        string='Segmento Venta',
        index=True,
    )
    dpp_value = fields.Float(string='DPP', digits=(16, 2))
    dpp_segment = fields.Selection(
        selection=[
            ('a', 'A'),
            ('b', 'B'),
            ('c', 'C'),
            ('no_dpp', 'Sin DPP'),
        ],
        string='Segmento DPP',
        index=True,
    )
    final_segment_label = fields.Char(
        string='Segmento Final',
        index=True,
    )
    target_amount = fields.Monetary(string='Meta Anual')
    monthly_target_amount = fields.Monetary(string='Meta Mensual')
    increase_amount = fields.Monetary(string='Incremento')
    current_sales_amount = fields.Monetary(string='Venta Actual')
    average_monthly_sales = fields.Monetary(string='Promedio Mensual')
    monthly_gap_amount = fields.Monetary(string='Crecimiento Mensual')
    projected_sales_amount = fields.Monetary(string='Proyeccion')
    compliance_percent = fields.Float(string='Cumplimiento', digits=(16, 4))
    achievement_gap_percent = fields.Float(string='Desviacion vs Meta', digits=(16, 4))
    budget_amount = fields.Monetary(string='Presupuesto Objetivo')
    notes = fields.Text(string='Notas')

    _sql_constraints = [
        (
            'sng_commercial_plan_line_unique_partner',
            'unique(plan_id, partner_id)',
            'Cada cliente solo puede existir una vez por plan.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = [self._normalize_vals(vals) for vals in vals_list]
        return super().create(normalized_vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('partner_id'):
            vals = self._normalize_vals(vals)
        return super().write(vals)

    @api.model
    def _normalize_vals(self, vals):
        values = dict(vals)
        partner_id = values.get('partner_id')
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id).commercial_partner_id
            values['partner_id'] = partner.id
            values.update(self._prepare_partner_snapshot_vals(partner))
        return values

    @api.model
    def _prepare_partner_snapshot_vals(self, partner):
        partner = partner.commercial_partner_id
        partner_fields = partner._fields
        code = False
        salesperson = False
        commercial_name = partner.display_name

        if 'unique_id' in partner_fields:
            code = partner.unique_id
        else:
            code = partner.ref

        if 'commercial_name' in partner_fields:
            commercial_name = partner.commercial_name or partner.display_name
        elif 'comercial_name' in partner_fields:
            commercial_name = partner.comercial_name or partner.display_name

        if 'assigned_salesperson_id' in partner_fields:
            salesperson = partner.assigned_salesperson_id.id
        elif 'user_id' in partner_fields:
            salesperson = partner.user_id.id

        return {
            'customer_code': code or False,
            'commercial_name': commercial_name or False,
            'assigned_salesperson_id': salesperson or False,
        }
