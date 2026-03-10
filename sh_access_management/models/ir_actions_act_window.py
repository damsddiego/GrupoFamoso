# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models
import xml.etree.ElementTree as ET

class IRactioonsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def read(self, fields=None, load='_classic_read'):
        result = super(IRactioonsActWindow, self).read(fields, load=load)
        if self.env.user.has_group('base.group_system'):
            return result
            
        if result and 'view_mode' in result[0]:
            allowed_views = []
            if ',' in result[0].get('view_mode'):
                allowed_views = result[0].get('view_mode').split(',')
            else:
                allowed_views = [result[0].get('view_mode')]
            find_model = False
            domain = [('model', '=', 'sh.access.manager')]
            find_model = self.env['ir.model'].sudo().search(domain)
            if find_model:
                user_domain = [
                    ('active_rule', '=', True),
                    ('sh_restriction_type', '=', 'user'),
                    ('responsible_user_ids', 'in', self.env.user.ids),
                    ('company_id', '=', self.env.company.id)
                ]
                group_domain = [
                    ('active_rule', '=', True),
                    ('sh_restriction_type', '=', 'group'),
                    ('responsible_group_ids', 'in', self.env.user.groups_id.ids),
                    ('company_id', '=', self.env.company.id)
                ]
                domain = ['|'] + user_domain + group_domain
                find_access = self.env['sh.access.manager'].sudo().search(domain)
                if find_access:
                    view_list = []
                    for model_access in find_access.sh_access_model_line:
                        if model_access.sudo().model_id.model == result[0].get('res_model'):
                            for allowed in allowed_views:
                                for views in model_access.view_ids:
                                    if allowed == views.technical_name and views.technical_name not in view_list:
                                        view_list.append(views.technical_name)
                    for views in view_list:
                        for allowed in allowed_views:
                            if allowed == views:
                                del allowed_views[allowed_views.index(allowed)]
                    result[0]['view_mode'] = ','.join(allowed_views)
                    if 'views' in result[0]:
                        view_ids = []
                        for view_id in result[0].get('views'):
                            if view_id[1] in allowed_views:
                                view_ids.append(view_id)
                        result[0]['views'] = view_ids
        return result