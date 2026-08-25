# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: authentication and web-client gates.

* _check_credentials denies login when the user is in any active
  profile with disable_login = True.
* The disable_debug_mode toggle is enforced by an override of the
  /web web_client controller route in controllers/web.py because the
  debug flag lives on the URL, not on the user record.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    access_profile_ids = fields.Many2many(
        "eh.access.profile",
        "eh_access_profile_user_rel",
        "user_id",
        "profile_id",
        string="Access Studio Profiles",
        readonly=True,
    )

    def _check_credentials(self, credential, user_agent_env):
        # Run the standard credential check first.
        result = super()._check_credentials(credential, user_agent_env)
        try:
            self._eh_access_studio_check_login_disabled()
        except AccessDenied:
            raise
        except Exception:
            _logger.exception(
                "Access Studio: login gate failed for user %s",
                self.login,
            )
        return result

    def _eh_access_studio_check_login_disabled(self):
        if "eh.access.profile" not in self.env:
            return
        # Skip for SU and admin to keep recovery paths open.
        if self.env.su:
            return
        admin_groups = (
            self.env.ref("base.group_system", raise_if_not_found=False),
            self.env.ref("base.group_erp_manager", raise_if_not_found=False),
        )
        for group in admin_groups:
            if not group:
                continue
            # Walk the user record's group set so we catch implied
            # membership (e.g. admin via group_system implies
            # group_user). Doing the check from the user side avoids
            # divergence between Odoo 16/17/18 ('user_ids') and Odoo 19
            # ('all_user_ids') field naming.
            user_groups = (
                getattr(self, "all_group_ids", None)
                or getattr(self, "group_ids", None)
                or getattr(self, "groups_id", self.env["res.groups"].browse())
            )
            if group.id in user_groups.ids:
                return
        today = fields.Date.context_today(self)
        blocking = self.env["eh.access.profile"].sudo().search([
            ("disable_login", "=", True),
            ("active", "=", True),
            ("user_ids", "in", self.id),
            "|", ("date_from", "=", False),
            ("date_from", "<=", today),
            "|", ("date_until", "=", False),
            ("date_until", ">=", today),
        ], limit=1)
        if blocking:
            _logger.info(
                "Access Studio: login denied for %s due to profile %s",
                self.login, blocking.name,
            )
            try:
                blocking.sudo().message_post(body=_(
                    "Login denied for %(user)s.",
                    user=self.login,
                ))
            except Exception:
                # Audit failure must not turn a denial into a 500.
                _logger.exception(
                    "Access Studio: failed to post login-denial audit"
                    " message on profile %s",
                    blocking.name,
                )
            raise AccessDenied(_(
                "Sign-in is disabled for this account by an Access"
                " Studio profile."
            ))
