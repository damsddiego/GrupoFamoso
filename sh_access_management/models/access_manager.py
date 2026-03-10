# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from markupsafe import Markup

from odoo import _, api, exceptions, fields, models
from odoo.tools import html_escape


class AccessManager(models.Model):
    """
        A class to manage the access of users.
    """
    _name = "sh.access.manager"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Access Management"

    name = fields.Char("Name", tracking=True)

    sh_restriction_type = fields.Selection([
        ('user', 'User'),
        ('group', 'Group'),
    ], default='user', string='Restriction Type', tracking=True)

    responsible_user_ids = fields.Many2many(
        'res.users',
        'sh_access_manager_responsible_user_rel',
        'sh_access_manager_id',
        'responsible_user_id',
        string="Users",
        tracking=True)

    responsible_group_ids = fields.Many2many(
        'res.groups',
        'sh_access_manager_responsible_group_rel',
        'sh_access_manager_id',
        'responsible_group_id',
        string="Groups",
        tracking=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    created_by = fields.Many2one(
        "res.users", string="Created By", tracking=True)
    active_rule = fields.Boolean("Active", default=True, tracking=True)
    sh_expiry_date = fields.Date("Expiry Date", tracking=True)
    sh_readonly = fields.Boolean("Readonly", tracking=True)
    sh_disable_developer_mode = fields.Boolean(
        "Disable Developer Mode", tracking=True)

    sh_global_hide_full_chatter = fields.Boolean(
        "Full Chatter", tracking=True)
    sh_disable_user_login = fields.Boolean("Disable Login", tracking=True)

    # Global Access
    sh_global_hide_add_property = fields.Boolean(
        "Hide Add Property", tracking=True)
    sh_global_hide_import = fields.Boolean("Hide Import", tracking=True)
    sh_global_hide_export = fields.Boolean(
        "Hide Export", tracking=True)
    sh_global_hide_print_button = fields.Boolean(
        "Hide Print Button", tracking=True)
    sh_global_hide_action_button = fields.Boolean(
        "Hide Action Button", tracking=True)
    sh_global_hide_send_message = fields.Boolean(
        "Hide Send Message", tracking=True)
    sh_global_hide_log_note = fields.Boolean("Hide Log note", tracking=True)
    sh_global_hide_activity = fields.Boolean("Hide Activity", tracking=True)
    sh_global_hide_search_message_icon = fields.Boolean("Hide Search Message Icon", tracking=True)
    sh_global_hide_attachment_icon = fields.Boolean("Hide Attachment Icon", tracking=True)
    sh_global_hide_followers_icon = fields.Boolean("Hide Followers Icon", tracking=True)
    sh_global_hide_follow_unfollow_button = fields.Boolean("Hide Follow/Unfollow Button", tracking=True)
    sh_global_hide_filter = fields.Boolean("Hide Filter", tracking=True)
    sh_global_hide_group = fields.Boolean("Hide Group", tracking=True)
    sh_global_hide_custom_filter_option = fields.Boolean(
        "Hide Custom Filter Option", tracking=True)
    sh_global_hide_custom_group_by_option = fields.Boolean(
        "Hide Custom Group By Option", tracking=True)
    sh_global_hide_spreadsheet = fields.Boolean(
        "Hide Spreadsheet", tracking=True)
    sh_global_hide_field_credit_edit = fields.Boolean(
        "Hide Create / Edit", tracking=True)
    sh_global_hide_favorite_delete = fields.Boolean(
        "Hide Favorite Delete", tracking=True)

    sh_global_hide_create = fields.Boolean("Hide Create", tracking=True)
    sh_global_hide_delete = fields.Boolean("Hide Delete", tracking=True)
    sh_global_hide_duplicate = fields.Boolean("Hide Duplicate", tracking=True)
    sh_global_hide_archive = fields.Boolean("Hide Archive", tracking=True)
    sh_global_hide_unarchive = fields.Boolean("Hide Unarchive", tracking=True)

    sh_is_spreadsheet_installed = fields.Boolean(
        compute="_compute_is_spreadsheet_installed",
        store=False
    )

    @api.depends_context("uid")
    def _compute_is_spreadsheet_installed(self):
        installed = self.env['ir.module.module'].sudo().search_count([
            ("name", "=", "spreadsheet_edition"),
            ("state", "=", "installed"),
        ]) > 0
        for rec in self:
            rec.sh_is_spreadsheet_installed = installed

    # Pages
    sh_hide_menu_ids = fields.Many2many(
        comodel_name="ir.ui.menu",
        string="Hide Menu",
        tracking=True)

    sh_access_model_line = fields.One2many(
        "sh.access.model", 'access_manager_id', string="Access Model",
        tracking=True)

    sh_field_access_line = fields.One2many(
        "sh.field.access", 'access_manager_id', string="Field Access",
        tracking=True)

    sh_navbar_button_line = fields.One2many(
        'sh.navbar.buttons.access', 'access_manager_id', 'Navbar Button Access',
        tracking=True)

    sh_hide_chatter_line = fields.One2many(
        "sh.hide.chatter", 'access_manager_id', string="Hide Chatters",
        tracking=True)

    sh_hide_filter_line = fields.One2many(
        "sh.filter.access", 'access_manager_id', string="Filter Access",
        tracking=True)

    @api.model
    def sh_check_rule_expiry(self):
        """
            A method to check rule expiry.
        """
        rules = self.search([('sh_expiry_date', '!=', False)])
        for rule in rules:
            if rule.sh_expiry_date <= fields.Date.today():
                rule.active_rule = False

    @api.model_create_multi
    def create(self, vals_list):
        """
        Prevent adding admin users in `responsible_user_ids` during record creation.
        """
        admin_users = self.env.ref('base.group_system').users

        for vals in vals_list:
            if 'responsible_user_ids' in vals:
                new_user_ids = set()

                for operation in vals['responsible_user_ids']:
                    if operation[0] == 6:  # Replace all
                        new_user_ids.update(operation[2])
                    elif operation[0] == 4:  # Add single
                        new_user_ids.add(operation[1])

                restricted_admins = admin_users.filtered(
                    lambda u: u.id in new_user_ids)
                if restricted_admins:
                    raise exceptions.UserError(
                        _("You cannot add an administrator to the a list.")
                    )

        return super().create(vals_list)

    def _mail_track(self, tracked_fields, initial_values):
        """
            A method to track mail.
        """
        # Step 1: Remove One2many fields before calling super
        filtered_fields = {
            k: v for k, v in tracked_fields.items()
            if v.get('type') != 'one2many'
        }
        filtered_initial_values = {
            k: v for k, v in initial_values.items()
            if k in filtered_fields
        }

        return super()._mail_track(filtered_fields, filtered_initial_values)

    def write(self, vals):
        """
            A method to write values.
        """
        # Prevent assigning admin users
        if 'responsible_user_ids' in vals:
            admin_users = self.env.ref('base.group_system').users
            for record in self:
                new_user_ids = set()
                for operation in vals['responsible_user_ids']:
                    if operation[0] == 6:
                        new_user_ids.update(operation[2])
                    elif operation[0] == 4:
                        new_user_ids.add(operation[1])
                restricted_admins = admin_users.filtered(
                    lambda u: u.id in new_user_ids)
                if restricted_admins:
                    raise exceptions.UserError(
                        _("You cannot add an Administrator to the a list."))

        # Collect inline-created O2M record placeholders before write
        created_map = {}  # {record.id: {field_name: count}}

        for rec in self:
            for field_name, field in self._fields.items():
                if field.type == 'one2many' and field_name in vals:
                    commands = vals[field_name]
                    count = sum(1 for cmd in commands if cmd[0]
                              == 0 and isinstance(cmd[2], dict))
                    if count:
                        created_map.setdefault(rec.id, {})[field_name] = count

        res = super().write(vals)

        # Post-write: log correct records per field
        for rec in self:
            if rec.id in created_map:
                for field_name, count in created_map.get(rec.id, {}).items():
                    new_recs = rec[field_name].sorted(
                        key='id', reverse=True)[:count]
                    # to restore original order
                    new_recs = new_recs.sorted(key='id')

                    for new in new_recs:
                        model_desc = self.env[new._name]._description or new._name
                        msg_content = _("New → %(name)s,%(id)s (%(model_desc)s)") % {
                            'name': html_escape(new._name),
                            'id': new.id,
                            'model_desc': html_escape(model_desc)
                        }
                        msg = Markup(
                            "<ul><li><b>%(msg_content)s</b></li></ul>") % {
                                'msg_content': msg_content}
                        rec.message_post(body=msg, subtype_xmlid="mail.mt_note")

        self.env.registry.clear_cache()
        return res

    def unlink(self):
        """
            A method to unlink.
        """
        self.sh_navbar_button_line.unlink()
        return super().unlink()

    @api.model
    def get_access_restrictions(self, kwargs):
        """
        Dynamically prepare and return access restrictions for the user.
        Args:
            kwargs (dict): Contains user_id and optional company_id.
        Returns:
            dict: Restrictions based on user-specific and global rules.
        """
        user_id = kwargs.get("user_id")
        company_id = kwargs.get("company_id") or self.env.company.id

        if not user_id:
            raise ValueError("User ID is required.")

        user = self.env['res.users'].browse(user_id)
        if user.has_group('base.group_system'):
            return {"model_restrictions": {}}

        user_domain = [
            ('sh_restriction_type', '=', 'user'),
            ('responsible_user_ids', 'in', [user_id]),
            ('active_rule', '=', True),
        ]
        group_domain = [
            ('sh_restriction_type', '=', 'group'),
            ('responsible_group_ids', 'in', user.groups_id.ids),
            ('active_rule', '=', True),
        ]

        if company_id:
            user_domain.append(('company_id', '=', company_id))
            group_domain.append(('company_id', '=', company_id))

        domain = ['|'] + user_domain + group_domain

        disable_developer_mode = self.search_count(
            domain + [('sh_disable_developer_mode', '=', True)]) > 0
        global_hide_full_chatter = self.search_count(
            domain + [('sh_global_hide_full_chatter', '=', True)]) > 0
        sh_readonly = self.search_count(
            domain + [('sh_readonly', '=', True)]) > 0

        global_hide_custom_filter = self.search_count(
            domain + [('sh_global_hide_custom_filter_option', '=', True)]) > 0
        global_hide_custom_group_by = self.search_count(
            domain + [('sh_global_hide_custom_group_by_option', '=', True)]) > 0
        global_hide_filter = self.search_count(
            domain + [('sh_global_hide_filter', '=', True)]) > 0
        global_hide_group_by = self.search_count(
            domain + [('sh_global_hide_group', '=', True)]) > 0

        global_hide_spreadsheet = self.search_count(
            domain + [('sh_global_hide_spreadsheet', '=', True)]) > 0
        
        sh_global_hide_field_credit_edit = self.search_count(
            domain + [('sh_global_hide_field_credit_edit', '=', True)]) > 0

        sh_global_hide_favorite_delete = self.search_count(
            domain + [('sh_global_hide_favorite_delete', '=', True)]) > 0

        sh_global_hide_create = self.search_count(
            domain + [('sh_global_hide_create', '=', True)]) > 0

        sh_global_hide_delete = self.search_count(
            domain + [('sh_global_hide_delete', '=', True)]) > 0
        sh_global_hide_duplicate = self.search_count(
            domain + [('sh_global_hide_duplicate', '=', True)]) > 0
        sh_global_hide_archive = self.search_count(
            domain + [('sh_global_hide_archive', '=', True)]) > 0
        sh_global_hide_unarchive = self.search_count(
            domain + [('sh_global_hide_unarchive', '=', True)]) > 0

        return {
            "model_restrictions": {
                "disable_developer_mode": disable_developer_mode,
                "global_hide_full_chatter": global_hide_full_chatter,
                "sh_readonly": sh_readonly,
                "global_hide_custom_filter": global_hide_custom_filter,
                "global_hide_custom_group_by": global_hide_custom_group_by,
                "global_hide_filter": global_hide_filter,
                "global_hide_group_by": global_hide_group_by,
                "global_hide_spreadsheet": global_hide_spreadsheet,
                "sh_global_hide_field_credit_edit": sh_global_hide_field_credit_edit,
                "sh_global_hide_favorite_delete": sh_global_hide_favorite_delete,
                "sh_global_hide_create": sh_global_hide_create,
                "sh_global_hide_delete": sh_global_hide_delete,
                "sh_global_hide_duplicate": sh_global_hide_duplicate,
                "sh_global_hide_archive": sh_global_hide_archive,
                "sh_global_hide_unarchive": sh_global_hide_unarchive,
            }
        }