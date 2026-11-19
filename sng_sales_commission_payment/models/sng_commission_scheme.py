# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SngCommissionScheme(models.Model):
    _name = 'sng.commission.scheme'
    _description = 'Cuadro de Comisiones'
    _order = 'name, date_start desc, id'

    name = fields.Char(string='Nombre', required=True)
    company_ids = fields.Many2many(
        'res.company',
        'sng_commission_scheme_company_rel',
        'scheme_id',
        'company_id',
        string='Compañías',
        required=True,
        default=lambda self: self.env.company,
        help='El vendedor tiene una sola comisión al mes que suma lo cobrado '
             'en todas estas compañías.',
    )
    date_start = fields.Date(
        string='Vigente desde',
        help='Primer mes en que rige este cuadro. Vacío: desde siempre. Para una '
             'compañía y un mes rige el cuadro activo con la fecha más reciente '
             'que no pase de ese mes.',
    )
    tier_ids = fields.One2many(
        'sng.commission.tier',
        'scheme_id',
        string='Tramos',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        compute='_compute_currency_id',
    )
    active = fields.Boolean(default=True)
    company_names = fields.Char(
        string='Compañías del Cuadro',
        compute='_compute_company_names',
        compute_sudo=True,
        help='Para mostrar las compañías sin exigir que el usuario las tenga todas activas.',
    )

    @api.depends('company_ids.name')
    def _compute_company_names(self):
        for scheme in self:
            scheme.company_names = ', '.join(scheme.company_ids.mapped('name'))

    @api.depends('company_ids')
    def _compute_currency_id(self):
        for scheme in self:
            scheme.currency_id = scheme.company_ids[:1].currency_id

    @api.constrains('company_ids', 'date_start', 'active')
    def _check_companies(self):
        for scheme in self:
            if not scheme.company_ids:
                raise ValidationError(_(
                    "El cuadro %(name)s debe tener al menos una compañía.", name=scheme.name))
            if len(scheme.company_ids.mapped('currency_id')) > 1:
                raise ValidationError(_(
                    "Las compañías del cuadro %(name)s deben tener la misma moneda.", name=scheme.name))
            if not scheme.active:
                continue
            # sudo: otro cuadro con la misma compañía puede no estar a la
            # vista del usuario por la regla multicompañía.
            other = self.sudo().search([
                ('active', '=', True),
                ('id', '!=', scheme.id),
                ('company_ids', 'in', scheme.company_ids.ids),
                ('date_start', '=', scheme.date_start or False),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    "El cuadro %(other)s ya incluye a %(companies)s con la misma fecha de "
                    "vigencia. Cambie la fecha de «Vigente desde» o archive el otro cuadro.",
                    other=other.name,
                    companies=', '.join((other.company_ids & scheme.company_ids).mapped('name')),
                ))

    @api.model
    def _sng_first_of_month(self, vals):
        """La vigencia siempre es el primer día de un mes."""
        if vals.get('date_start'):
            vals = dict(vals, date_start=fields.Date.to_date(vals['date_start']).replace(day=1))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._sng_first_of_month(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._sng_first_of_month(vals))

    def action_regroup_open_months(self):
        """Pasa las comisiones pendientes al cuadro que rige hoy para cada
        compañía (ver ``sng.commission.monthly._sng_regroup_open``)."""
        if not (self.env.is_superuser() or self.env.user.has_group(
                'sales_commission_omax.group_sales_commission_manager')):
            raise AccessError(_("Solo un administrador de comisiones puede reagrupar los meses abiertos."))
        result = self.env['sng.commission.monthly']._sng_regroup_open()
        message = _(
            "%(lines)s líneas movidas, %(created)s comisiones creadas y %(removed)s eliminadas.",
            lines=result['moved_lines'], created=result['created_monthlies'],
            removed=result['removed_monthlies'])
        if result['skipped']:
            message += ' ' + _(
                "Sin mover, por tener un mes ya cerrado: %(names)s.",
                names=', '.join(sorted({
                    '%s (%s)' % (row['salesperson'].name, row['period'].strftime('%m/%Y'))
                    for row in result['skipped']})))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Meses abiertos reagrupados"),
                'message': message,
                'type': 'warning' if result['skipped'] else 'success',
                'sticky': bool(result['skipped']),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @api.model
    def _get_for_company(self, company, period):
        """Cuadro que rige para la compañía en el mes de ``period``: el activo
        que la incluye con la vigencia más reciente que no pase de ese mes
        (sin fecha cuenta como el más antiguo). Vacío si no hay ninguno."""
        return self.search([
            ('active', '=', True),
            ('company_ids', 'in', company.ids),
            '|', ('date_start', '=', False), ('date_start', '<=', period.replace(day=1)),
        ], order='date_start desc nulls last, id desc', limit=1)
