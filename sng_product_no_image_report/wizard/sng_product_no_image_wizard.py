# -*- coding: utf-8 -*-

from odoo import fields, models


class SngProductNoImageWizard(models.TransientModel):
    _name = 'sng.product.no.image.wizard'
    _description = 'Wizard — Artículos sin Imagen'

    company_ids = fields.Many2many(
        'res.company', string='Compañías',
        default=lambda self: self.env.companies)
    include_shared = fields.Boolean(
        string='Incluir productos compartidos', default=True,
        help='Productos sin compañía asignada, visibles en todas las empresas.')
    categ_id = fields.Many2one(
        'product.category', string='Categoría',
        help='Incluye las categorías hijas.')
    type = fields.Selection(
        [('consu', 'Bien'), ('service', 'Servicio'), ('combo', 'Combo')],
        string='Tipo')
    only_sale_ok = fields.Boolean(string='Solo los que se venden', default=False)
    only_purchase_ok = fields.Boolean(string='Solo los que se compran', default=False)
    only_with_code = fields.Boolean(string='Solo con código interno', default=False)

    def action_view_report(self):
        """Abrir el reporte con el dominio armado desde el wizard."""
        self.ensure_one()
        domain = []

        if self.company_ids:
            if self.include_shared:
                domain += ['|', ('company_id', '=', False),
                           ('company_id', 'in', self.company_ids.ids)]
            else:
                domain.append(('company_id', 'in', self.company_ids.ids))
        elif not self.include_shared:
            domain.append(('company_id', '!=', False))

        if self.categ_id:
            domain.append(('categ_id', 'child_of', self.categ_id.id))
        if self.type:
            domain.append(('type', '=', self.type))
        if self.only_sale_ok:
            domain.append(('sale_ok', '=', True))
        if self.only_purchase_ok:
            domain.append(('purchase_ok', '=', True))
        if self.only_with_code:
            domain += ['&', ('default_code', '!=', False),
                       ('default_code', '!=', '')]

        ctx = dict(self.env.context)
        ctx['allowed_company_ids'] = self.company_ids.ids or self.env.companies.ids
        ctx['search_default_group_company'] = 1

        return {
            'name': 'Artículos sin Imagen',
            'type': 'ir.actions.act_window',
            'res_model': 'sng.product.no.image',
            'view_mode': 'list,pivot',
            'views': [(False, 'list'), (False, 'pivot')],
            'domain': domain,
            'context': ctx,
            'target': 'current',
        }
