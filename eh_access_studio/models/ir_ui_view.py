# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: view-arch overlay.

Per-tag post-processors hide individual nodes when an active rule
matches. Tags handled here:

* field   (invisible / readonly / required)
* label   (companion to a field that is invisible)
* button  (object / action)
* page    (notebook tab)
* a       (kanban link)
* filter  (search filter)
* group   (search group-by inside <group>)

Heavy view-arch attribute injection (create / edit / delete /
import / export_xlsx) and toolbar pruning happen on `base` directly
in models/base_model.py because they apply to the response shape, not
to a per-tag walk.

Caching: the per-tag walkers all call _eh_access_field_rules and
_eh_access_node_rules. Both are wrapped with tools.ormcache keyed on
(uid, cid, today_iso, model_name) so a form view with N field tags
issues one DB lookup, not N. The cache is invalidated on profile / line
change via eh.access.profile._invalidate_active_cache.
"""
import ast
import logging

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

_RELATIONAL_TTYPES = frozenset((
    "many2one", "many2many", "one2many",
))


def _safe_call(self, fetcher, label, *args):
    """Run a rule-fetcher with logged exceptions instead of raising."""
    try:
        return fetcher(*args)
    except Exception:
        _logger.exception(
            "Access Studio: %s rules lookup failed", label,
        )
        return None


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    # ---- field rules (cached) -----------------------------------------

    @api.model
    @tools.ormcache("uid", "cid", "today_iso", "model_name")
    def _eh_access_field_rules(self, uid, cid, today_iso, model_name):
        """Return {field_name: {invisible/readonly/required}} for the
        active profile set under (uid, cid, today_iso) on `model_name`.

        Caches on the four key dimensions so a form-render walks the DB
        once per (user, company, day, model).
        """
        Profile = self.env["eh.access.profile"].sudo()
        profile_ids = Profile._get_active_profile_ids(uid, cid, today_iso)
        if not profile_ids:
            return {}
        lines = self.env["eh.access.field"].sudo().search([
            ("profile_id", "in", list(profile_ids)),
            ("model_name", "=", model_name),
        ])
        rules = {}
        for line in lines:
            for field in line.field_ids:
                bucket = rules.setdefault(field.name, {
                    "invisible": False,
                    "readonly": False,
                    "required": False,
                    "hide_external_link": False,
                    "ttype": field.ttype,
                })
                if line.invisible:
                    bucket["invisible"] = True
                if line.readonly:
                    bucket["readonly"] = True
                if line.required:
                    bucket["required"] = True
                if line.hide_external_link:
                    bucket["hide_external_link"] = True
        return rules

    @api.model
    @tools.ormcache("uid", "cid", "today_iso", "model_name")
    def _eh_access_node_rules(self, uid, cid, today_iso, model_name):
        """Return {kind: frozenset(target_name)} for the active set."""
        Profile = self.env["eh.access.profile"].sudo()
        profile_ids = Profile._get_active_profile_ids(uid, cid, today_iso)
        if not profile_ids:
            return {}
        lines = self.env["eh.access.node"].sudo().search([
            ("profile_id", "in", list(profile_ids)),
            ("model_name", "=", model_name),
        ])
        bucket = {}
        for line in lines:
            bucket.setdefault(line.kind, set()).add(line.target_name)
        return {k: frozenset(v) for k, v in bucket.items()}

    # ---- helpers used by the post-processors --------------------------

    def _eh_args(self):
        """Return (uid, cid, today_iso) for cache lookups."""
        Profile = self.env["eh.access.profile"].sudo()
        return (
            self.env.user.id,
            self.env.company.id,
            Profile._today_for_cache_key(),
        )

    def _eh_field_rules(self, model_name):
        uid, cid, today_iso = self._eh_args()
        return _safe_call(
            self, self._eh_access_field_rules, "field",
            uid, cid, today_iso, model_name,
        )

    def _eh_node_rules(self, model_name):
        uid, cid, today_iso = self._eh_args()
        return _safe_call(
            self, self._eh_access_node_rules, "node",
            uid, cid, today_iso, model_name,
        )

    # ---- field nodes --------------------------------------------------

    def _postprocess_tag_field(self, node, name_manager, node_info):
        super()._postprocess_tag_field(node, name_manager, node_info)
        rules = self._eh_field_rules(name_manager.model._name)
        if not rules:
            return
        bucket = rules.get(node.get("name"))
        if not bucket:
            return
        if bucket["invisible"]:
            node.set("invisible", "1")
            node.set("column_invisible", "True")
            node_info["invisible"] = True
            node_info["column_invisible"] = True
        if bucket["readonly"]:
            node.set("readonly", "1")
            node.set("force_save", "1")
            node_info["readonly"] = True
        if bucket["required"]:
            node.set("required", "1")
            node_info["required"] = True
        if bucket.get("hide_external_link") and bucket.get("ttype") in _RELATIONAL_TTYPES:
            self._eh_inject_no_link_options(node)

    @staticmethod
    def _eh_inject_no_link_options(node):
        """Merge `no_open`, `no_create`, `no_edit` into the field's
        widget options attribute. Preserves any existing keys."""
        raw = node.get("options") or ""
        existing = {}
        if raw:
            try:
                parsed = ast.literal_eval(raw)
                if isinstance(parsed, dict):
                    existing = parsed
            except (SyntaxError, ValueError):
                return
        existing.setdefault("no_open", True)
        existing.setdefault("no_create", True)
        existing.setdefault("no_edit", True)
        node.set("options", str(existing))

    def _postprocess_tag_label(self, node, name_manager, node_info):
        super()._postprocess_tag_label(node, name_manager, node_info)
        target = node.get("for")
        if not target:
            return
        rules = self._eh_field_rules(name_manager.model._name)
        bucket = rules.get(target) if rules else None
        if bucket and bucket["invisible"]:
            node.set("invisible", "1")
            node_info["invisible"] = True

    # ---- button / page / link / filter / group ------------------------
    #
    # Odoo 19's ir.ui.view does NOT define post-processors for these
    # tags by default (only for field, label, form, list, search,
    # calendar, groupby). The framework's tag dispatcher
    # (ir_ui_view._postprocess_view, the
    # `getattr(self, f"_postprocess_tag_{tag}")` lookup) picks our
    # methods up automatically because we name them correctly. We do
    # NOT call super() because the parent has no method with these
    # names; calling super raises AttributeError.

    def _postprocess_tag_button(self, node, name_manager, node_info):
        rules = self._eh_node_rules(name_manager.model._name)
        if not rules:
            return
        if node.get("name") in rules.get("button", frozenset()):
            node.set("invisible", "1")
            node_info["invisible"] = True

    def _postprocess_tag_page(self, node, name_manager, node_info):
        rules = self._eh_node_rules(name_manager.model._name)
        if not rules:
            return
        if node.get("name") in rules.get("page", frozenset()):
            node.set("invisible", "1")
            node_info["invisible"] = True

    def _postprocess_tag_a(self, node, name_manager, node_info):
        rules = self._eh_node_rules(name_manager.model._name)
        if not rules:
            return
        target = node.get("name") or node.get("data-name")
        if target and target in rules.get("link", frozenset()):
            node.set("invisible", "1")
            node_info["invisible"] = True

    def _postprocess_tag_filter(self, node, name_manager, node_info):
        rules = self._eh_node_rules(name_manager.model._name)
        if not rules:
            return
        target = node.get("name")
        if not target:
            return
        if (target in rules.get("filter", frozenset())
                or target in rules.get("group", frozenset())):
            node.set("invisible", "1")
            node_info["invisible"] = True
