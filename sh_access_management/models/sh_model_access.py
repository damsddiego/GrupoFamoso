# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import html_escape


class AccessManager(models.Model):
    """
        A class to manage the access of models.
    """
    _name = "sh.access.model"
    _description = "Model wise Restriction"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    model_id = fields.Many2one('ir.model', string="Model", tracking=True)

    view_ids = fields.Many2many(
        'sh.view.list', string="Hide Views", tracking=True)

    access_manager_id = fields.Many2one(
        "sh.access.manager", string="Access Manager", tracking=True)

    report_ids = fields.Many2many(
        'ir.actions.report',
        domain="[('binding_model_id','=',model_id)]",
        string="Hide Reports",
        tracking=True)

    action_id = fields.Many2one(
        comodel_name="ir.actions.actions",
        domain="[('binding_model_id','=',model_id),('binding_type', '=', 'action')]",
        string="Hide Actions",
        tracking=True)

    hide_create = fields.Boolean("Hide Create Button", tracking=True)
    hide_edit = fields.Boolean("Hide Edit Button", tracking=True)
    hide_duplicate = fields.Boolean("Hide Duplicate Button", tracking=True)
    hide_delete = fields.Boolean("Hide Delete Button", tracking=True)
    hide_archieve = fields.Boolean("Hide Archive Button", tracking=True)
    hide_export = fields.Boolean("Hide Export Button", tracking=True)

    sh_hide_action = fields.Boolean("Hide All Actions", tracking=True)
    sh_hide_print = fields.Boolean("Hide Print Button", tracking=True)
    hide_spreadsheet = fields.Boolean("Hide Spreadsheet", tracking=True)

    @api.model
    def check_crud_operation(self, kwargs):
        """
        A method to check crud operation.
        """
        user_id = kwargs.get('user_id')
        if not user_id:
            return {}

        user = self.env['res.users'].browse(user_id)
        # Bypass for system/admin users
        if self.env.su or user.has_group('base.group_system'):
            return {}

        company_id = kwargs.get("company_id") or self.env.company.id

        user_domain = [
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'user'),
            ('access_manager_id.responsible_user_ids', 'in', [int(user_id)]),
            ('access_manager_id.company_id', '=', company_id)
        ]
        group_domain = [
            ('access_manager_id.active_rule', '=', True),
            ('access_manager_id.sh_restriction_type', '=', 'group'),
            ('access_manager_id.responsible_group_ids', 'in', user.groups_id.ids),
            ('access_manager_id.company_id', '=', company_id)
        ]
        domain = ['|'] + user_domain + group_domain

        find_model_access = self.env['sh.access.model'].sudo().search(domain)
        model_data = {}

        # Per Model Specific Rules (unchanged)
        if find_model_access:
            model_list = []
            for rec in find_model_access:
                model_name = rec.model_id.sudo().model
                if model_name not in model_list:
                    model_list.append(model_name)
                    records = find_model_access.filtered(
                        lambda x: x.model_id == rec.model_id
                    )

                    model_data[model_name] = {
                        'hide_create': any(records.mapped("hide_create")) or False,
                        'hide_edit': any(records.mapped("hide_edit")) or False,
                        'hide_duplicate': any(records.mapped("hide_duplicate")) or False,
                        'hide_delete': any(records.mapped("hide_delete")) or False,
                        'hide_archieve': any(records.mapped("hide_archieve")) or False,
                        'hide_export': any(records.mapped("hide_export")) or False,
                        'hide_spreadsheet': any(records.mapped("hide_spreadsheet")) or False,
                    }

        # Global Settings (from access.manager)
        manager_user_domain = [
            ('active_rule', '=', True),
            ('sh_restriction_type', '=', 'user'),
            ('responsible_user_ids', 'in', [int(user_id)]),
            ('company_id', '=', company_id)
        ]
        manager_group_domain = [
            ('active_rule', '=', True),
            ('sh_restriction_type', '=', 'group'),
            ('responsible_group_ids', 'in', user.groups_id.ids),
            ('company_id', '=', company_id)
        ]
        manager_domain = ['|'] + manager_user_domain + manager_group_domain
        access_managers = self.env['sh.access.manager'].sudo().search(manager_domain)

        if access_managers:
            readonly = any(access_managers.mapped("sh_readonly"))

            global_data = {
                # these already had correct meaning
                'hide_import': any(access_managers.mapped('sh_global_hide_import')) or False,
                'hide_export': any(access_managers.mapped('sh_global_hide_export')) or False,
                'hide_spreadsheet': any(access_managers.mapped('sh_global_hide_spreadsheet')) or False,

                # ✅ FIX: use any(), not not any()
                'hide_custom_filter_option': any(access_managers.mapped('sh_global_hide_custom_filter_option')) or False,
                'hide_add_property': any(access_managers.mapped('sh_global_hide_add_property')) or False,
                'hide_print': any(access_managers.mapped('sh_global_hide_print_button')) or False,
                'hide_action': any(access_managers.mapped('sh_global_hide_action_button')) or False,

                'sh_readonly': readonly,

                # other global flags you already had
                'sh_global_hide_create': any(access_managers.mapped('sh_global_hide_create')) or False,
                'sh_global_hide_delete': any(access_managers.mapped('sh_global_hide_delete')) or False,
                'sh_global_hide_duplicate': any(access_managers.mapped('sh_global_hide_duplicate')) or False,
                'sh_global_hide_archive': any(access_managers.mapped('sh_global_hide_archive')) or False,
                'sh_global_hide_unarchive': any(access_managers.mapped('sh_global_hide_unarchive')) or False,
            }

            model_data['__global__'] = global_data

        return model_data


    def write(self, vals):
        """
        A method to write values.
        """
        if self._context.get('disable_child_tracking_forward'):
            return super().write(vals)

        tracked_fields = [
            f for f in vals
            if f in self._fields and getattr(self._fields[f], 'tracking', False)
        ]

        initial_values = {
            rec.id: {f: rec[f] for f in tracked_fields}
            for rec in self
        }

        res = super().write(vals)
        tracking_data = self._message_track(tracked_fields, initial_values)

        for rec in self:
            if rec.access_manager_id and rec.id in tracking_data:
                _, tracking_value_ids = tracking_data[rec.id]
                if tracking_value_ids:
                    field = self.env['ir.model.fields'].search([
                        ('model', '=', rec.access_manager_id._name),
                        ('relation', '=', rec._name),
                        ('ttype', '=', 'one2many')
                    ], limit=1)

                    parent_field_label = field.field_description or rec._name
                    display_label = html_escape(str(rec.id) or rec.name or rec.display_name)                         if rec.display_name else str(rec.id)

                    msg = Markup(
                        "<b>Update from One2many field: %s — Id: %s</b>") % (parent_field_label, display_label)

                    rec.access_manager_id.with_context(
                        disable_child_tracking_forward=True).message_post(
                        body=msg,
                        tracking_value_ids=tracking_value_ids,
                        subtype_xmlid='mail.mt_note'
                    )

        return res
