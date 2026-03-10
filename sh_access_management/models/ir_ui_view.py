# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, SUPERUSER_ID, _
from odoo.tools.translate import _
from lxml import etree
import ast

class ir_ui_view(models.Model):
    _inherit = 'ir.ui.view'


    def _postprocess_tag_search(self, node, name_manager, node_info):

        postprocessor = getattr(super(ir_ui_view, self), '_postprocess_tag_search', False)
        if postprocessor:
            super(ir_ui_view, self)._postprocess_tag_search(node, name_manager, node_info)

        if self.env.user.has_group('base.group_system'):
            return None

        all_actions = self.env['ir.actions.act_window'].sudo().search([('res_model', '=', name_manager.model._name),('search_view_id', '=', self.id)])

        # Fetch all filters and group-bys that need to be hidden
        user_domain = [
            ('model_id.model', '=', name_manager.model._name),
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids', 'in', self._uid),
            ('access_manager_id.company_id', '=', self.env.company.id),
        ]
        group_domain = [
            ('model_id.model', '=', name_manager.model._name),
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids', 'in', self.env.user.groups_id.ids),
            ('access_manager_id.company_id', '=', self.env.company.id),
        ]
        domain = ['|'] + user_domain + group_domain
        hide_filter_ids = self.env['sh.filter.access'].sudo().search(domain)

        hidden_filter_names = hide_filter_ids.mapped('sh_store_filter_data_ids.sh_attribute_name')
        hidden_groupby_names = hide_filter_ids.mapped('sh_store_groupby_data_ids.sh_attribute_name')

        removed_defaults_per_model = {}

        for action in all_actions:
            try:
                context_data = ast.literal_eval(action.context) if action.context else {}
            except Exception:
                context_data = {}

            sh_is_modified = False
            removed_defaults = {}

            # Remove default filters from context
            for hidden_filter in hidden_filter_names:
                key = f"search_default_{hidden_filter}"
                if key in context_data:
                    removed_defaults[key] = context_data.pop(key)
                    sh_is_modified = True

            # Remove default groupbys from context
            if 'group_by' in context_data:
                if isinstance(context_data['group_by'], str):
                    context_data['group_by'] = [context_data['group_by']]
                elif not isinstance(context_data['group_by'], list):
                    context_data['group_by'] = []

                new_group_by = [gb for gb in context_data['group_by'] if gb not in hidden_groupby_names]
                if len(new_group_by) < len(context_data['group_by']):
                    context_data['group_by'] = new_group_by
                    removed_defaults['group_by'] = hidden_groupby_names
                    sh_is_modified = True

            if sh_is_modified:
                action.sudo().write({'context': str(context_data)})

            if removed_defaults:
                removed_defaults_per_model[action.res_model] = removed_defaults

        # Hide filters/groupbys in XML node
        def recursive_hide_filters(xml_node):
            for child in xml_node:
                if 'invisible' in child.attrib:
                    del child.attrib['invisible']

                # Direct filter hiding
                if child.tag == 'filter':
                    name = child.get('name')
                    if name in hidden_filter_names or name in hidden_groupby_names:
                        child.set('invisible', '1')
                        node_info['invisible'] = "1 == 1"

                # Recurse into nested groups
                if child.tag == 'group':
                    recursive_hide_filters(child)

        recursive_hide_filters(node)

        # Store hidden context keys (optional debug or analytics)
        if removed_defaults_per_model:
            config_param = self.env['ir.config_parameter'].sudo()
            for model_name, removed_defaults in removed_defaults_per_model.items():
                config_param.set_param(f'hidden_defaults_{model_name}_{self.id}', str(removed_defaults))

        return None


    def _postprocess_tag_button(self, node, name_manager, node_info):
        # Hide Any Button
        postprocessor = getattr(super(ir_ui_view, self), '_postprocess_tag_button', False)
        if postprocessor:
            super(ir_ui_view, self)._postprocess_tag_button(node, name_manager, node_info)

        if self.env.user.has_group('base.group_system'):
            return None

        hide = None
        hide_button_obj = self.env['sh.navbar.buttons.access']
        
        user_domain = [
            ('model_id.model','=',name_manager.model._name),
            ('access_manager_id.active_rule','=',True),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids','in',self._uid),
            ('access_manager_id.company_id', '=', self.env.company.id)
        ]
        group_domain = [
            ('model_id.model','=',name_manager.model._name),
            ('access_manager_id.active_rule','=',True),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids','in',self.env.user.groups_id.ids),
            ('access_manager_id.company_id', '=', self.env.company.id)
        ]
        domain = ['|'] + user_domain + group_domain
        hide_button_ids = hide_button_obj.sudo().search(domain)

        # Filtered with same env user and current model
        sh_store_btn_data_ids = hide_button_ids.mapped('sh_store_btn_data_ids')
        # translation_obj = self.env['ir.translation']
        if sh_store_btn_data_ids:
            for btn in sh_store_btn_data_ids:
                if btn.sh_attribute_name == node.get('name'):
                    if node.get('string'):
                        # if translation_obj._get_source(None, ('model_terms',), self.env.lang, btn.sh_attribute_string, None) == node.get('string'):
                        if _(btn.sh_attribute_string) == node.get('string'):
                            hide = [btn]
                            break
                    else:
                        hide = [btn]
                        break
        if hide:
            node.set('invisible', '1')
            if 'attrs' in node.attrib.keys() and node.attrib['attrs']:
                del node.attrib['attrs']
            # node_info['modifiers']['invisible'] = True
            node_info['invisible'] = "1 == 1"

        return None
    
    def _postprocess_tag_page(self, node, name_manager, node_info):
        # Hide Any Notebook Page
        postprocessor = getattr(super(ir_ui_view, self), '_postprocess_tag_page', False)
        if postprocessor:
            super(ir_ui_view, self)._postprocess_tag_page(node, name_manager, node_info)

        if self.env.user.has_group('base.group_system'):
            return None

        hide = None
        hide_tab_obj = self.env['sh.navbar.buttons.access']
        user_domain = [
            ('model_id.model','=',name_manager.model._name),
            ('access_manager_id.active_rule','=',True),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids','in',self._uid),
            ('access_manager_id.company_id', '=', self.env.company.id)
        ]
        group_domain = [
            ('model_id.model','=',name_manager.model._name),
            ('access_manager_id.active_rule','=',True),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids','in',self.env.user.groups_id.ids),
            ('access_manager_id.company_id', '=', self.env.company.id)
        ]
        domain = ['|'] + user_domain + group_domain
        hide_tab_ids = hide_tab_obj.sudo().search(domain)
        
        # translation_obj = self.env['ir.translation']
        # Filtered with same env user and current model
        sh_store_page_data_ids = hide_tab_ids.mapped('sh_store_page_data_ids')
        if sh_store_page_data_ids:
            for tab in sh_store_page_data_ids:
                # query = """SELECT value FROM ir_translation WHERE lang=%s AND type in (code) AND src=%s"""
                # self._cr.execute(query, params)
                # res = self._cr.fetchone()
                
                # if translation_obj._get_source(None, ('model_terms',), self.env.lang, tab.sh_attribute_string, None) == node.get('string'):
                if _(tab.sh_attribute_string) == node.get('string'):
                    if node.get('name'):
                        if tab.sh_attribute_name == node.get('name'):
                            hide = [tab]
                            break
                    else:
                        hide = [tab]
                        break    
        if hide:
            node.set('invisible', '1')
            if 'attrs' in node.attrib.keys() and node.attrib['attrs']:
                del node.attrib['attrs']
      
            # node_info['modifiers']['invisible'] = True
            node_info['invisible'] = "1 == 1"
        return None

    def _postprocess_tag_a(self, node, name_manager, node_info):

        # Call super if exists
        _super = getattr(super(ir_ui_view, self), '_postprocess_tag_a', None)
        if _super:
            _super(node, name_manager, node_info)

        if self.env.user.has_group('base.group_system'):
            return None

        # Ensure it's kanban view only
        if self.type != 'kanban':
            return

        # Extract <a> tag properties
        link_name = node.get('name')
        link_text = ''.join(node.itertext()).strip()

        # Load hidden link rules from DB
        user_domain = [
            ('model_id.model', '=', name_manager.model._name),
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids', 'in', self.env.uid),
            ('access_manager_id.company_id', '=', self.env.company.id),
        ]
        group_domain = [
            ('model_id.model', '=', name_manager.model._name),
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids', 'in', self.env.user.groups_id.ids),
            ('access_manager_id.company_id', '=', self.env.company.id),
        ]
        domain = ['|'] + user_domain + group_domain
        access_rules = self.env['sh.navbar.buttons.access'].sudo().search(domain)

        match_found = False

        for rule in access_rules.mapped('sh_store_kanban_link_ids'):
            rule_name = rule.sh_attribute_name
            rule_string = rule.sh_attribute_string.strip()


            if (rule_name and rule_name == link_name) or (rule_string and rule_string == link_text):
                match_found = True
                break

        if match_found:
            # Hide the <a> tag by forcing invisible
            node.set('t-if', 'False')
            node_info['invisible'] = "1 == 1"
