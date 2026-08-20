# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: ir.rule._compute_domain extension.

We extend Odoo's built-in record-rule machinery so the domains we
store on eh.access.domain are AND-ed onto the standard rule domain
returned for each (model, mode) pair.

Why ir.rule and not BaseModel.create / write / unlink?
* ir.rule is the canonical, well-tested gate.
* It runs once per (model, mode) and is cached by Odoo.
* It applies to search, read, write and unlink without per-record
  Python checks.
* Users hitting the gate get Odoo's standard 'access denied' dialog.

Mode handling:
* read   uses the rule's domain when read_right is True
* create gates entirely (Odoo expects ALL-or-NONE on create)
* write  uses domain when write_right is True
* unlink uses domain when delete_right is True

A profile that does not grant a given right contributes a 'block all'
domain ([(id, '=', False)]) for that mode. The OR-across-rules
combinator below means any rule that grants the right opens the gate
for the records matching that rule's filter.

Domain composition uses the public `&` and `|` operators on
odoo.fields.Domain so we never depend on a specific class-method API
shape.
"""
import logging
from odoo import api, fields, models
from odoo.osv import expression

_logger = logging.getLogger(__name__)

BLOCK_ALL = [("id", "=", False)]
PASS_ALL = []  # empty domain matches every record


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _compute_domain(self, model_name, mode="read"):
        base_domain = super()._compute_domain(model_name, mode)

        # Skip extension when the call originates from our own resolver
        # to avoid recursion when the engine reads its own configuration
        # tables.
        if self.env.context.get("eh_access_studio_bypass"):
            return base_domain

        try:
            extra = self._eh_access_studio_domain(model_name, mode)
        except Exception:
            _logger.exception(
                "Access Studio: failed to compute domain for %s/%s",
                model_name, mode,
            )
            return base_domain

        if extra is None:
            return base_domain

        base_list = list(base_domain) if base_domain else []
        extra_list = list(extra) if isinstance(extra, (list, tuple)) else list(extra)
        if not base_list:
            return extra_list
        return expression.AND([base_list, extra_list])

    def _eh_access_studio_domain(self, model_name, mode):
        """Return the AND-extension to apply for the current user.

        Return value:
          * None   ... no extra restriction (most permissive)
          * Domain ... restrict to the records matching this domain
        """
        if "eh.access.profile" not in self.env:
            return None
        profile_model = self.env["eh.access.profile"].sudo()
        profile_ids = profile_model._get_active_profile_ids(
            self.env.user.id,
            self.env.company.id,
            profile_model._today_for_cache_key(),
        )
        if not profile_ids:
            return None

        # Skip our own configuration tables so admins don't lock
        # themselves out via a rule that targets eh.access.* itself.
        if model_name.startswith("eh.access."):
            return None

        rules = self.env["eh.access.domain"].sudo().with_context(
            eh_access_studio_bypass=True,
        ).search([
            ("profile_id", "in", list(profile_ids)),
            ("model_name", "=", model_name),
        ])
        if not rules:
            return None

        right_field = {
            "read": "read_right",
            "create": "create_right",
            "write": "write_right",
            "unlink": "delete_right",
        }.get(mode)
        if not right_field:
            return None

        # OR across rules: a user passes through if ANY rule grants the
        # right and the record matches that rule's filter. A rule that
        # does NOT grant the right contributes BLOCK_ALL for the OR;
        # a rule that grants the right with no filter contributes
        # PASS_ALL, which when OR-ed makes the whole result
        # unrestricted. We short-circuit to None in that case.
        today = fields.Date.context_today(self)
        leaves = []
        for rule in rules:
            if getattr(rule, right_field):
                resolved = rule._resolved_domain(today=today)
                if not resolved:
                    # PASS_ALL anywhere collapses the OR to no
                    # restriction.
                    return None
                leaves.append(resolved)
            else:
                leaves.append(BLOCK_ALL)

        if not leaves:
            return None

        # OR-combine via odoo.osv.expression.OR.
        return expression.OR([list(leaf) for leaf in leaves])
