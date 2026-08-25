# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: menu hiding.

The Odoo navigation calls ir.ui.menu.search_fetch to materialise the
menu tree. We post-filter that result by removing any menu listed on
an active profile for the current user. The empty-set short-circuit at
the top keeps the cost negligible for users with no profile.
"""
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        result = super().search_fetch(
            domain, field_names, offset=offset, limit=limit, order=order
        )
        Profile = self.env["eh.access.profile"].sudo()
        profile_ids = Profile._get_active_profile_ids(
            self.env.user.id,
            self.env.company.id,
            Profile._today_for_cache_key(),
        )
        if not profile_ids:
            return result
        hidden_ids = set(
            self.env["eh.access.profile"]
                .sudo()
                .browse(profile_ids)
                .mapped("hidden_menu_ids.id")
        )
        if not hidden_ids:
            return result
        # Drop the configuration menu from the hidden set so admins are
        # never locked out of their own configuration.
        own_menu = self.env.ref(
            "eh_access_studio.menu_eh_access_root", raise_if_not_found=False
        )
        if own_menu and own_menu.id in hidden_ids:
            hidden_ids.discard(own_menu.id)
        return result.filtered(lambda menu: menu.id not in hidden_ids)
