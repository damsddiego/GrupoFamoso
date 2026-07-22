# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SngCommissionTier(models.Model):
    _name = 'sng.commission.tier'
    _description = 'Tramo de Comisión (Cuadro de Comisiones)'
    _order = 'company_id, min_amount, id'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    min_amount = fields.Monetary(
        string='Monto Mínimo',
        required=True,
        currency_field='currency_id',
        help='El tramo aplica cuando el acumulado mensual (sin impuestos) es mayor o igual a este monto.',
    )
    percentage = fields.Float(
        string='Porcentaje de Comisión',
        required=True,
        help='Porcentaje aplicado sobre TODO el acumulado mensual cuando se alcanza este tramo.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Moneda',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'check_percentage_non_negative',
            'CHECK(percentage >= 0)',
            'El porcentaje de comisión no puede ser negativo.',
        ),
        (
            'check_min_amount_non_negative',
            'CHECK(min_amount >= 0)',
            'El monto mínimo no puede ser negativo.',
        ),
        (
            'unique_min_amount_company',
            'UNIQUE(company_id, min_amount)',
            'Ya existe un tramo con ese monto mínimo para la compañía.',
        ),
    ]

    @api.depends('min_amount', 'percentage')
    def _compute_name(self):
        for tier in self:
            tier.name = _(
                "Desde %(amount)s → %(percentage).2f%%",
                amount=int(tier.min_amount),
                percentage=tier.percentage,
            )

    @api.model
    def get_tier_for_amount(self, amount, company):
        """Devuelve el tramo aplicable (mayor min_amount <= amount) para la compañía."""
        return self.search(
            [
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('min_amount', '<=', amount),
            ],
            order='min_amount desc',
            limit=1,
        )

    @api.model
    def get_percentage_for_amount(self, amount, company):
        tier = self.get_tier_for_amount(amount, company)
        return tier.percentage if tier else 0.0
