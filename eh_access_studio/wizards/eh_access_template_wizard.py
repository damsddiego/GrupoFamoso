# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: profile-template wizard.

Bootstraps a new profile from one of a few well-tested scenarios that
cover the bulk of customer requests:

* read_only          read everywhere, no create / edit / delete
* own_records_only   read / edit own records on res.partner-style
                     models keyed on user_id
* vendor_portal      restricted to a small whitelist of menus and
                     records they own
* auditor            read access plus debug disabled, time-bounded

Each template is a small data factory: it knows the field bag to
write on eh.access.profile and the lines to attach. Template logic
lives in code (not data) so it can reference Odoo records (admin
groups, model lookups) without depending on XML data ordering.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


TEMPLATE_OPTIONS = [
    ("read_only", "Read-only across the system"),
    ("own_records_only", "Sales rep: own records only"),
    ("vendor_portal", "Vendor / contractor: portal-style restricted view"),
    ("auditor", "Auditor: read everything, no edit, no debug"),
]


class EhAccessTemplateWizard(models.TransientModel):
    _name = "eh.access.template.wizard"
    _description = "User Access Studio Template Wizard"

    template = fields.Selection(
        TEMPLATE_OPTIONS,
        required=True,
        default="own_records_only",
    )
    name = fields.Char(
        string="Profile name",
        required=True,
        help="The new profile is created with this name.",
    )
    user_ids = fields.Many2many(
        "res.users",
        string="Apply to users",
        help="Users assigned to the new profile.",
    )
    target_model = fields.Char(
        string="Target model (own-records template)",
        default="sale.order",
        help=(
            "For the 'own records only' template: the model whose"
            " records the user should be limited to. The template"
            " stamps a domain of [('user_id', '=', '__uid__')] on"
            " this model."
        ),
    )
    duration_days = fields.Integer(
        string="Duration in days (auditor template)",
        default=30,
        help=(
            "For the 'auditor' template: number of days the profile"
            " remains active. After that the daily cron deactivates it."
        ),
    )

    description = fields.Text(
        compute="_compute_description",
        readonly=True,
    )

    @api.depends("template")
    def _compute_description(self):
        descriptions = {
            "read_only": _(
                "Creates a profile with Read-Only Mode enabled. The"
                " user can browse the entire system but cannot create,"
                " edit or delete any record. Administrators are exempt."
            ),
            "own_records_only": _(
                "Creates a profile with a domain rule on the chosen"
                " model that limits read / edit to records where"
                " user_id equals the current user. Hides the export"
                " button on every model."
            ),
            "vendor_portal": _(
                "Creates a heavily restricted profile: hides the"
                " standard Settings menu, hides export everywhere,"
                " disables developer mode, and stamps a domain on"
                " sale.order limiting access to the user's own"
                " records."
            ),
            "auditor": _(
                "Creates a read-only profile with disable_debug_mode"
                " enabled and an Active Until date set to today plus"
                " the chosen number of days. After expiry the daily"
                " cron deactivates the profile."
            ),
        }
        for record in self:
            record.description = descriptions.get(record.template, "")

    def action_create_profile(self):
        self.ensure_one()
        if not self.name:
            raise UserError(_("Pick a name for the new profile."))
        builder = getattr(self, "_build_" + self.template, None)
        if builder is None:
            raise UserError(_("Unknown template: %(t)s.", t=self.template))
        vals = builder()
        profile = self.env["eh.access.profile"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "eh.access.profile",
            "view_mode": "form",
            "res_id": profile.id,
            "target": "current",
        }

    # -- builders -------------------------------------------------------

    def _base_vals(self):
        return {
            "name": self.name,
            "user_ids": [(6, 0, self.user_ids.ids)],
            "active": True,
        }

    def _build_read_only(self):
        vals = self._base_vals()
        vals.update({"readonly": True})
        return vals

    def _build_own_records_only(self):
        vals = self._base_vals()
        IrModel = self.env["ir.model"]
        target = IrModel.search([("model", "=", self.target_model)], limit=1)
        if not target:
            raise UserError(_(
                "Model %(m)s does not exist in this database.",
                m=self.target_model,
            ))
        vals.update({
            "hide_export": True,
            "domain_line_ids": [(0, 0, {
                "model_id": target.id,
                "read_right": True,
                "write_right": True,
                "create_right": False,
                "delete_right": False,
                "apply_filter": True,
                "domain": '[("user_id", "=", "__uid__")]',
            })],
        })
        return vals

    def _build_vendor_portal(self):
        vals = self._base_vals()
        IrModel = self.env["ir.model"]
        sale_model = IrModel.search([("model", "=", "sale.order")], limit=1)
        Menu = self.env["ir.ui.menu"]
        settings_menu = Menu.search([
            ("name", "=", "Settings"),
            ("parent_id", "=", False),
        ], limit=1)
        line_specs = []
        if sale_model:
            line_specs.append((0, 0, {
                "model_id": sale_model.id,
                "read_right": True,
                "create_right": False,
                "write_right": False,
                "delete_right": False,
                "apply_filter": True,
                "domain": '[("user_id", "=", "__uid__")]',
            }))
        vals.update({
            "hide_export": True,
            "hide_import": True,
            "hide_spreadsheet": True,
            "disable_debug_mode": True,
            "hidden_menu_ids": [(6, 0, settings_menu.ids if settings_menu else [])],
            "domain_line_ids": line_specs,
        })
        return vals

    def _build_auditor(self):
        vals = self._base_vals()
        days = max(1, int(self.duration_days or 30))
        today = fields.Date.context_today(self)
        vals.update({
            "readonly": True,
            "disable_debug_mode": True,
            "date_from": today,
            "date_until": today + timedelta(days=days),
        })
        return vals
