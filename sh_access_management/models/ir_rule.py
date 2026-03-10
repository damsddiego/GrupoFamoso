# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, tools, fields, _
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, AccessError

class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain(self, model_name, mode="read"):
        """
        Extend `_compute_domain` to add restrictions for `create`, `write`, and `delete`
        operations based on `sh.access.manager`. If restricted, raise `UserError`.
        """
        global_domains = []  # list of global domains

        # Add rules for parent models
        for parent_model_name, parent_field_name in self.env[model_name]._inherits.items():
            if domain := self._compute_domain(parent_model_name, mode):
                global_domains.append([(parent_field_name, 'any', domain)])

        rules = self._get_rules(model_name, mode=mode)
        if not rules:
            return expression.AND(global_domains) if global_domains else []

        # Evaluate user groups and rules
        eval_context = self._eval_context()
        user_groups = self.env.user.groups_id
        group_domains = []  # list of group-specific domains

        for rule in rules.sudo():
            # Evaluate the domain for the current user
            dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
            dom = expression.normalize_domain(dom)
            if not rule.groups:
                global_domains.append(dom)
            elif rule.groups & user_groups:
                group_domains.append(dom)

        # **Restrict create, write, delete using SQL Query**
        if mode in ['write', 'create', 'unlink']:
            self.env.cr.execute("""
                SELECT COUNT(*) 
                FROM sh_access_manager AS access
                JOIN sh_access_manager_responsible_user_rel AS rel 
                ON access.id = rel.sh_access_manager_id
                WHERE rel.responsible_user_id = %s
                AND access.active_rule = TRUE
                AND access.sh_readonly = TRUE
            """, [self.env.user.id])

            restricted_count = self.env.cr.fetchone()[0]

            # If user is restricted, RAISE UserError instead of blocking access silently
            if restricted_count > 0:
                raise UserError(_('🚫 You have read-only access and are not permitted to modify any records.'))

        # Combine global domains and group domains
        if not group_domains:
            return expression.AND(global_domains)
        return expression.AND(global_domains + [expression.OR(group_domains)])
