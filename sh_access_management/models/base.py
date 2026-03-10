# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import json
import logging
from lxml import etree

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class Model(models.AbstractModel):
    """
        A class to manage the access of models.
    """
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        """
            A method to get views.
        """
        res = super().get_views(views, options)

        if self.env.user.has_group('base.group_system'):
            return res

        self.env.registry.clear_cache()

        model_name = None
        for value in res.get("views", {}).values():
            if isinstance(value, dict) and "model" in value:
                model_name = value["model"]
                break

        if not model_name or not res.get('views'):
            return res

        # Identify One2many Fields in the Parent Model
        one2many_fields = {}
        for view_data in res['views'].values():
            if 'arch' in view_data:
                root = etree.fromstring(view_data['arch'])
                for field_elem in root.iter('field'):
                    field_name = field_elem.attrib.get('name')
                    field_info = self.env[model_name]._fields.get(field_name)
                    if field_info and field_info.type == 'one2many':
                        one2many_fields[field_name] = field_info.comodel_name

        models_to_check = [model_name] + list(one2many_fields.values())

        user_domain = [
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.company_id', '=', self.env.company.id),
            ('model_id.model', 'in', models_to_check),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids', 'in', self.env.user.ids)
        ]
        group_domain = [
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.company_id', '=', self.env.company.id),
            ('model_id.model', 'in', models_to_check),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids', 'in', self.env.user.groups_id.ids)
        ]
        domain = ['|'] + user_domain + group_domain

        find_field_access = self.env['sh.field.access'].sudo().search(domain)

        field_access_rules = {
            (access.model_id.model, field.name): access
            for access in find_field_access
            for field in access.field_ids
        }

        for view_type, view_data in res['views'].items():
            if 'arch' in view_data:
                root = etree.fromstring(view_data['arch'])

                is_tree_view = view_type in ['list']

                # Apply access rules on parent fields
                for field_elem in root.xpath(".//field[not(ancestor::field)]"):
                    field_name = field_elem.attrib.get('name')
                    access_rule = field_access_rules.get(
                        (model_name, field_name))
                    if access_rule:
                        if access_rule.invisible:
                            field_elem.set("invisible", "1")
                            if is_tree_view:
                                field_elem.set("column_invisible", "1")
                        if access_rule.readonly:
                            field_elem.set("readonly", "1")
                        if access_rule.required:
                            field_elem.set("required", "1")
                        if access_rule.sh_hide_external_links:
                            options_attr = field_elem.attrib.get(
                                'options', "{}")
                            try:
                                options_dict = json.loads(
                                    options_attr.replace("'", '"'))
                            except json.JSONDecodeError:
                                options_dict = {}
                            options_dict.update(
                                {"no_open": True})
                            field_elem.attrib['options'] = json.dumps(
                                options_dict)
                        if access_rule.sh_hide_create_edit:
                            field_elem.set("can_create", "0")
                            field_elem.set("can_write", "0")

                # Child (One2many) fields
                for parent_field, child_model in one2many_fields.items():
                    xpath = f".//field[@name='{parent_field}']//field[not(ancestor::field[@name='{parent_field}']//field[@name='{parent_field}'])]"
                    for child_field_elem in root.xpath(xpath):
                        child_field_name = child_field_elem.attrib.get('name')
                        child_access_rule = field_access_rules.get(
                            (child_model, child_field_name))
                        if child_access_rule:
                            if child_access_rule.invisible:
                                child_field_elem.set("column_invisible", "1")
                                child_field_elem.set("invisible", "1")
                            if child_access_rule.readonly:
                                child_field_elem.set("readonly", "1")
                            if child_access_rule.required:
                                child_field_elem.set("required", "1")
                            if child_access_rule.sh_hide_external_links:
                                options_attr = child_field_elem.attrib.get(
                                    'options', "{}")
                                try:
                                    options_dict = json.loads(
                                        options_attr.replace("'", '"'))
                                except json.JSONDecodeError:
                                    options_dict = {}
                                options_dict.update(
                                    {"no_open": True})
                                child_field_elem.attrib['options'] = json.dumps(
                                    options_dict)
                            if child_access_rule.sh_hide_create_edit:
                                child_field_elem.set("can_create", "0")
                                child_field_elem.set("can_write", "0")

                                if child_field_elem.attrib.get('widget') is None:
                                    field_info = self.env[child_model]._fields.get(
                                        child_field_name)
                                    if field_info and field_info.type == 'many2one':
                                        child_field_elem.attrib['widget'] = 'many2one'

                # Update the modified XML back to result
                view_data['arch'] = etree.tostring(
                    root, encoding='unicode').replace('\t', '')

        self.env.registry.clear_cache()
        return res

    @api.model
    def create(self, vals):
        """
            A method to create a record.
        """
        # Bypass all our custom checks for superusers or members of the 'Administration/Settings' group.
        if self.env.su or self.env.user.has_group('base.group_system'):
            return super().create(vals)

        # Do not apply restrictions to the access manager models themselves to prevent lock-outs.
        if self._name in ['sh.access.manager', 'sh.access.model', 'sh.view.list', 'sh.field.access']:
            return super().create(vals)

        access_rules = self.env['sh.access.model'].check_crud_operation({
            'user_id': self.env.user.id,
            'company_id': self.env.company.id
        })

        if not access_rules:
            return super().create(vals)

        model_name = self._name

        # 1. Check for a global read-only rule.
        global_rules = access_rules.get('__global__', {})
        if global_rules:
            is_readonly = global_rules.get('sh_readonly')
            if is_readonly:
                raise AccessError(
                    _("🚫 You have read-only access and are not permitted to modify any records."))

        # 2. Check for model-specific rules.
        model_specific_rules = access_rules.get(model_name)
        if model_specific_rules:
            rule_val = model_specific_rules.get('hide_create')
            if rule_val is True:
                raise AccessError(
                    _("🚫 You have read-only access and are not permitted to modify any records."))

        return super().create(vals)