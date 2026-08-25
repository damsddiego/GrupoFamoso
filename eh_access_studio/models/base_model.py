# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: response-shape overlays on `base`.

The post-processors in models/ir_ui_view.py walk the arch tag-by-tag.
Two operations don't fit that pattern and live here instead:

* _get_view: stamps view-level attributes (create / delete / edit /
  import / export_xlsx) on the root <list>, <form>, <kanban> nodes.
  These attributes are read by the JS layer to render or hide the
  respective buttons.

* get_views: prunes the toolbar dictionary returned to the client so
  that hidden report and server actions do not appear in the cog menu.

The _get_view_cache_key override is also here because cache-keying
applies to the response, not to a per-tag walk. Sharing the key by
profile rather than by uid means two users on the same profile share
the cached arch.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


_VIEWS_WITH_CRUD = frozenset((
    "form", "list", "kanban", "calendar", "gantt", "pivot", "graph",
    "activity", "cohort", "grid", "map", "hierarchy",
))
_VIEWS_WITH_IMPORT_EXPORT = frozenset(("list", "kanban"))


class BaseAccessStudio(models.AbstractModel):
    _inherit = "base"

    def _eh_access_studio_active_profile_ids(self):
        if "eh.access.profile" not in self.env:
            return ()
        Profile = self.env["eh.access.profile"].sudo()
        try:
            return Profile._get_active_profile_ids(
                self.env.user.id,
                self.env.company.id,
                Profile._today_for_cache_key(),
            )
        except Exception:
            # Defensive: a missing table during install or any other
            # transient issue must not break the view-render path.
            _logger.exception(
                "Access Studio: active-profile lookup failed for"
                " user %s company %s; returning empty.",
                self.env.user.id, self.env.company.id,
            )
            return ()

    def _eh_access_studio_model_lines(self):
        """Return eh.access.model lines for self / current user.

        Uses the cached eh.access.profile._model_line_ids_for so a
        burst of view renders does one DB lookup per (user, company,
        day, model).
        """
        if "eh.access.profile" not in self.env:
            return self.env["eh.access.model"].sudo().browse()
        Profile = self.env["eh.access.profile"].sudo()
        try:
            line_ids = Profile._model_line_ids_for(
                self.env.user.id,
                self.env.company.id,
                Profile._today_for_cache_key(),
                self._name,
            )
        except Exception:
            _logger.exception(
                "Access Studio: model-lines lookup failed for %s",
                self._name,
            )
            return self.env["eh.access.model"].sudo().browse()
        return self.env["eh.access.model"].sudo().browse(line_ids)

    def _eh_access_studio_global_profile(self):
        """Return the most permissive readonly / global-toggle profile in
        the active set, or browse() of nothing.

        Used to short-circuit when the user is in a read-only profile or
        has any of the global hide_* toggles enabled.
        """
        profile_ids = self._eh_access_studio_active_profile_ids()
        if not profile_ids:
            return self.env["eh.access.profile"].sudo().browse()
        return self.env["eh.access.profile"].sudo().browse(profile_ids)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        profile_ids = self._eh_access_studio_active_profile_ids()
        if not profile_ids:
            return key
        return key + (("eh_access_studio", profile_ids, self.env.company.id),)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        try:
            self._eh_access_studio_apply_view_attrs(arch, view_type)
        except Exception:
            _logger.exception(
                "Access Studio: failed to apply view attrs for %s/%s",
                self._name, view_type,
            )
        return arch, view

    def _eh_access_studio_apply_view_attrs(self, arch, view_type):
        profiles = self._eh_access_studio_global_profile()
        if not profiles:
            return

        readonly_active = any(profiles.mapped("readonly"))
        model_lines = self._eh_access_studio_model_lines()

        if view_type == "form":
            self._eh_access_studio_strip_chatter(arch, profiles)

        if view_type not in _VIEWS_WITH_CRUD:
            return

        if readonly_active:
            arch.attrib["create"] = "false"
            arch.attrib["delete"] = "false"
            arch.attrib["edit"] = "false"

        if model_lines:
            for attr, flag in (
                ("create", "restrict_create"),
                ("delete", "restrict_delete"),
                ("edit", "restrict_edit"),
            ):
                if any(model_lines.mapped(flag)):
                    arch.attrib[attr] = "false"

            if view_type in _VIEWS_WITH_IMPORT_EXPORT:
                if any(model_lines.mapped("restrict_import")):
                    arch.attrib["import"] = "false"
                if any(model_lines.mapped("restrict_export")):
                    arch.attrib["export_xlsx"] = "false"

        if view_type in _VIEWS_WITH_IMPORT_EXPORT:
            if any(profiles.mapped("hide_import")):
                arch.attrib["import"] = "false"
            if any(profiles.mapped("hide_export")):
                arch.attrib["export_xlsx"] = "false"

        # Duplicate is controlled by the `duplicate` attribute on the
        # root form node. The JS form controller reads it via
        # exprToBoolean(rootNode.getAttribute("duplicate"), true).
        if view_type == "form" and model_lines:
            if any(model_lines.mapped("restrict_duplicate")):
                arch.attrib["duplicate"] = "false"

    def _eh_access_studio_strip_chatter(self, arch, profiles):
        """Remove chatter widget when profile rules say so."""
        global_hide = any(profiles.mapped("hide_chatter"))
        per_model_hide = False
        if not global_hide:
            chatter_lines = self.env["eh.access.chatter"].sudo().search([
                ("profile_id", "in", profiles.ids),
                ("model_name", "=", self._name),
            ], limit=1)
            per_model_hide = bool(chatter_lines)
        if not (global_hide or per_model_hide):
            return
        for chatter in arch.xpath("//chatter"):
            parent = chatter.getparent()
            if parent is not None:
                parent.remove(chatter)

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options=options)
        try:
            self._eh_access_studio_prune_toolbars(result)
        except Exception:
            _logger.exception(
                "Access Studio: failed to prune toolbars for %s",
                self._name,
            )
        return result

    def _eh_access_studio_prune_toolbars(self, view_response):
        model_lines = self._eh_access_studio_model_lines()
        if not model_lines:
            return
        hidden_print = set(model_lines.mapped("hidden_report_action_ids.id"))
        hidden_action = set(model_lines.mapped("hidden_server_action_ids.id"))
        hidden_view_types = set()
        for line in model_lines:
            hidden_view_types.update(line._hidden_view_type_set())

        if not (hidden_print or hidden_action or hidden_view_types):
            return

        views_dict = view_response.get("views") or {}
        for view_type in list(views_dict.keys()):
            if view_type in hidden_view_types:
                views_dict.pop(view_type, None)
                continue
            view_data = views_dict.get(view_type) or {}
            toolbar = view_data.get("toolbar")
            if not toolbar:
                continue
            if hidden_print and toolbar.get("print"):
                toolbar["print"] = [
                    entry for entry in toolbar["print"]
                    if entry.get("id") not in hidden_print
                ]
            if hidden_action and toolbar.get("action"):
                toolbar["action"] = [
                    entry for entry in toolbar["action"]
                    if entry.get("id") not in hidden_action
                ]

    # ---- archive / duplicate enforcement at the ORM gate --------------
    #
    # The form-controller duplicate button reads the view's `duplicate`
    # attribute (set above) so users in a restrict_duplicate profile do
    # not see the menu entry. We still guard at copy() in case a custom
    # button or RPC call bypasses the front-end. Archive is the same
    # story: the cog menu item is gated client-side by the absence of
    # an `active` field write right, but we re-check in toggle_active
    # to defend against direct calls.

    def _eh_access_studio_check_op(self, attr):
        """Raise AccessError if any active model line has the named
        restrict flag set for self's model.

        attr is one of restrict_archive / restrict_duplicate. Skips
        SUPERUSER_ID and admins so recovery paths stay open."""
        if not self or self.env.su or self.env.uid == 1:
            return
        if "eh.access.profile" not in self.env:
            return
        model_lines = self._eh_access_studio_model_lines()
        if not model_lines:
            return
        if any(model_lines.mapped(attr)):
            label = "archive" if attr == "restrict_archive" else "duplicate"
            raise AccessError(_(
                "Access Studio: %(action)s is disabled for this model"
                " by your access profile.",
                action=label,
            ))

    def toggle_active(self):
        self._eh_access_studio_check_op("restrict_archive")
        return super().toggle_active()

    def copy(self, default=None):
        self._eh_access_studio_check_op("restrict_duplicate")
        return super().copy(default=default)
