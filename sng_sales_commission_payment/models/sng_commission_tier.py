# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SngCommissionTier(models.Model):
    _name = 'sng.commission.tier'
    _description = 'Tramo de Comisión (Cuadro de Comisiones)'
    _order = 'scheme_id, min_amount, id'

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
    scheme_id = fields.Many2one(
        'sng.commission.scheme',
        string='Cuadro',
        required=True,
        index=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='scheme_id.currency_id',
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
            'unique_min_amount_scheme',
            'UNIQUE(scheme_id, min_amount)',
            'Ya existe un tramo con ese monto mínimo en el cuadro.',
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
    def get_tier_for_amount(self, amount, scheme):
        """Devuelve el tramo aplicable (mayor min_amount <= amount) del cuadro."""
        return self.search(
            [
                ('scheme_id', '=', scheme.id),
                ('active', '=', True),
                ('min_amount', '<=', amount),
            ],
            order='min_amount desc',
            limit=1,
        )

    @api.model
    def get_percentage_for_amount(self, amount, scheme):
        tier = self.get_tier_for_amount(amount, scheme)
        return tier.percentage if tier else 0.0
