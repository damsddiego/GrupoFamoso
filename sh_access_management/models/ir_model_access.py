# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, tools, _
from odoo.exceptions import UserError, AccessError

class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    # For Make Global Read Only User.
    @tools.ormcache('self.env.uid', 'mode')
    def _get_allowed_models(self, mode='read'):
        """
        Extend `_get_allowed_models` to enforce dynamic read-only restrictions,
        but allow administrators to bypass these restrictions.
        """
        assert mode in ('read', 'write', 'create', 'unlink'), 'Invalid access mode'
        self.env.registry.clear_cache()

        # Bypass for admin (superuser) or users in Administration/Settings group
        if self.env.su or self.env.user.has_group('base.group_system'):
            return super()._get_allowed_models(mode)

        user = self.env.user
        # Use raw SQL query for better performance
        query = """
            SELECT COUNT(*) 
            FROM sh_access_manager AS access
            WHERE access.active_rule = TRUE AND access.sh_readonly = TRUE
            AND (
                (
                    access.sh_restriction_type = 'user'
                    AND access.id IN (
                        SELECT sh_access_manager_id 
                        FROM sh_access_manager_responsible_user_rel 
                        WHERE responsible_user_id = %s
                    )
                )
                OR
                (
                    access.sh_restriction_type = 'group'
                    AND access.id IN (
                        SELECT sh_access_manager_id 
                        FROM sh_access_manager_responsible_group_rel 
                        WHERE responsible_group_id IN %s
                    )
                )
            )
        """
        params = [user.id, tuple(user.groups_id.ids)]

        if self.env.company:
            query += " AND access.company_id = %s"
            params.append(self.env.company.id)

        self.env.cr.execute(query, params)
        restricted_count = self.env.cr.fetchone()[0]

        # If restricted and mode is 'write', 'create', or 'unlink', deny access
        if restricted_count > 0 and mode in ['write', 'create', 'unlink']:
            return frozenset()  # Return an empty set to block access

        return super()._get_allowed_models(mode)

    # By Pass Base Default Access Error Message and give our ReadOnly Access Error Message. 
    def _make_access_error(self, model: str, mode: str):
        """ Override method to modify access error message based on custom domain conditions. """
        
        user = self.env.user
        if user.has_group('base.group_system'):
            return super()._make_access_error(model, mode)

        # Execute the SQL query to check for read-only access restriction
        query = """
            SELECT COUNT(*)
            FROM sh_access_manager AS access
            WHERE access.active_rule = TRUE AND access.sh_readonly = TRUE
            AND (
                (
                    access.sh_restriction_type = 'user'
                    AND access.id IN (
                        SELECT sh_access_manager_id
                        FROM sh_access_manager_responsible_user_rel
                        WHERE responsible_user_id = %s
                    )
                )
                OR
                (
                    access.sh_restriction_type = 'group'
                    AND access.id IN (
                        SELECT sh_access_manager_id
                        FROM sh_access_manager_responsible_group_rel
                        WHERE responsible_group_id IN %s
                    )
                )
            )
        """
        params = [user.id, tuple(user.groups_id.ids)]

        if self.env.company:
            query += " AND access.company_id = %s"
            params.append(self.env.company.id)

        self.env.cr.execute(query, params)
        restricted_count = self.env.cr.fetchone()[0]

        # If the user has a read-only restriction and is trying to modify data, block the action
        if restricted_count > 0 and mode in ['write', 'create', 'unlink']:
            return AccessError(_("🚫 You have read-only access and are not permitted to modify any records."))

        return super()._make_access_error(model, mode)
