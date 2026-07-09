# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SngCommissionConfig(models.Model):
    _name = 'sng.commission.config'
    _description = 'Configuración de Comisión por Vendedor'
    _order = 'salesperson_id, start_date, id'

    salesperson_id = fields.Many2one(
        'res.partner',
        string='Vendedor',
        required=True,
        domain="[('is_salesperson', '=', True)]",
        index=True,
    )
    percentage = fields.Float(
        string='Porcentaje de Comisión',
        required=True,
        help='Porcentaje aplicado sobre el monto sin impuestos pagado.',
    )
    start_date = fields.Date(
        string='Fecha Inicio',
        help='Fecha de inicio de vigencia. Si está vacío, no tiene límite inicial.',
    )
    end_date = fields.Date(
        string='Fecha Fin',
        help='Fecha de fin de vigencia. Si está vacío, no tiene límite final.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'check_percentage_positive',
            'CHECK(percentage > 0)',
            _('El porcentaje de comisión debe ser mayor a 0.'),
        ),
        (
            'check_date_order',
            'CHECK(start_date IS NULL OR end_date IS NULL OR end_date >= start_date)',
            _('La fecha fin debe ser mayor o igual a la fecha inicio.'),
        ),
    ]

    @api.constrains('salesperson_id', 'company_id', 'start_date', 'end_date')
    def _check_overlap(self):
        for record in self:
            domain = [
                ('id', '!=', record.id),
                ('salesperson_id', '=', record.salesperson_id.id),
                ('company_id', '=', record.company_id.id),
                ('active', '=', True),
            ]
            if record.start_date:
                domain += ['|', ('end_date', '>=', record.start_date), ('end_date', '=', False)]
            if record.end_date:
                domain += ['|', ('start_date', '<=', record.end_date), ('start_date', '=', False)]
            if not record.start_date and not record.end_date:
                # Si ambas están vacías, cualquier otro registro activo se solapa.
                pass
            overlapping = self.search(domain)
            if overlapping:
                raise ValidationError(_(
                    "Ya existe una configuración de comisión vigente para el vendedor %(salesperson)s en el rango de fechas seleccionado.",
                    salesperson=record.salesperson_id.name,
                ))

    def get_percentage_for_date(self, date):
        self.ensure_one()
        if self.start_date and date < self.start_date:
            return 0.0
        if self.end_date and date > self.end_date:
            return 0.0
        return self.percentage
