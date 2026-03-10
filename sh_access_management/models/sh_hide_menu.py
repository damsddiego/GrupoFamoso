# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models

class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    sh_child_menu = fields.Many2one("ir.ui.menu", string="Hide Menu", tracking=True)

    @api.model
    def get_menus_to_hide(self, company_ids):

        if not list(company_ids):
            company_ids = list(company_ids)
        if not company_ids or not company_ids[0]:
            return []

        if self.env.user.has_group('base.group_system'):
            return []

        # If only one company is active, the logic is simple.
        if company_ids[0]:
            user_domain = [
                ('active_rule', '=', True),
                ('sh_restriction_type', '=', 'user'),
                ('responsible_user_ids', 'in', self.env.user.ids),
                ('company_id', '=', company_ids[0]),
            ]
            group_domain = [
                ('active_rule', '=', True),
                ('sh_restriction_type', '=', 'group'),
                ('responsible_group_ids', 'in', self.env.user.groups_id.ids),
                ('company_id', '=', company_ids[0]),
            ]
            domain = ['|'] + user_domain + group_domain
            access_records = self.env['sh.access.manager'].sudo().search(domain)
            self.env.registry.clear_cache('routing')
            self.env.registry.clear_cache('assets')
            self.env.registry.clear_cache('templates')
            return access_records.mapped('sh_hide_menu_ids').ids

        # For multiple companies, find menus that are hidden in ALL of them.
        hidden_menus_per_company = []
        for company_id in company_ids:
            user_domain = [
                ('active_rule', '=', True),
                ('sh_restriction_type', '=', 'user'),
                ('responsible_user_ids', 'in', self.env.user.ids),
                ('company_id', '=', company_id),
            ]
            group_domain = [
                ('active_rule', '=', True),
                ('sh_restriction_type', '=', 'group'),
                ('responsible_group_ids', 'in', self.env.user.groups_id.ids),
                ('company_id', '=', company_id),
            ]
            domain = ['|'] + user_domain + group_domain
            access_records = self.env['sh.access.manager'].sudo().search(domain)
            hidden_menus_per_company.append(set(access_records.mapped('sh_hide_menu_ids').ids))

        if not hidden_menus_per_company:
            return []

        # The final list of menus to hide is the intersection of all the sets.
        final_hidden_set = set.intersection(*hidden_menus_per_company)
        
        return list(final_hidden_set)

    # @api.returns('self')
    # def _filter_visible_menus(self):
    #
    #     self.env.registry.clear_cache('routing')
    #     self.env.registry.clear_cache('assets')
    #     self.env.registry.clear_cache('templates')
    #     res = super(IrUiMenu, self)._filter_visible_menus()
    #     if res and self.env.user:
    #         domain = [('active_rule', '=', True),('responsible_user_ids', 'in', self.env.user.ids),('company_id', '=', self.env.company.id)]
    #         access_records = self.env['sh.access.manager'].sudo().search(domain)
    #         if access_records:
    #             menu_ids = access_records.mapped('sh_hide_menu_ids').ids
    #             return res.filtered(lambda m: m.id not in menu_ids)
    #     return res
