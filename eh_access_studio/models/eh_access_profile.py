# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: profile model.

A profile is a named, activatable bundle of access overlays applied to
one or more users. The profile owns three kinds of rule lines:

* hidden_menu_ids: many2many of menus to remove from the navigation
* field_line_ids:  one2many of per-model field hide / readonly / required
* (more lines added in later phases: model, domain, node, search, chatter)

Active profiles are resolved per (uid, cid) and cached. The cache is
invalidated on profile create, write and unlink.

Cache invalidation pattern: ormcache keyed on uid and cid is used so
that two users on the same profile share view caches (unlike a per-uid
cache key which fragments the cache).
"""
import logging

import psycopg2

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EhAccessProfile(models.Model):
    _name = "eh.access.profile"
    _description = "User Access Studio Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "active desc, sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="Short human-readable label shown in administration screens.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    readonly = fields.Boolean(
        string="Read-Only Mode",
        tracking=True,
        help=(
            "When enabled, users in this profile cannot create, edit or"
            " delete records anywhere in the system. The Access Studio"
            " configuration is excluded so administrators are never locked"
            " out."
        ),
    )

    user_ids = fields.Many2many(
        "res.users",
        "eh_access_profile_user_rel",
        "profile_id",
        "user_id",
        string="Users",
        help="Users to whom this profile applies.",
    )
    company_ids = fields.Many2many(
        "res.company",
        "eh_access_profile_company_rel",
        "profile_id",
        "company_id",
        string="Companies",
        default=lambda self: self.env.company,
        help=(
            "Profile applies only when the user is currently logged into"
            " one of these companies. Leave empty when 'Apply to all"
            " companies' is enabled."
        ),
    )
    apply_to_all_companies = fields.Boolean(
        string="Apply to all companies",
        default=True,
        help=(
            "When enabled, the profile applies regardless of the user's"
            " current company. The Companies field is ignored."
        ),
    )

    date_from = fields.Date(
        string="Active From",
        help=(
            "Optional start date. Profile is treated as inactive before"
            " this date."
        ),
    )
    date_until = fields.Date(
        string="Active Until",
        help=(
            "Optional end date. A scheduled action deactivates the"
            " profile when this date has passed."
        ),
    )

    hidden_menu_ids = fields.Many2many(
        "ir.ui.menu",
        "eh_access_profile_menu_rel",
        "profile_id",
        "menu_id",
        string="Hidden Menus",
        help=(
            "Menus and submenus removed from the navigation for users in"
            " this profile."
        ),
    )

    field_line_ids = fields.One2many(
        "eh.access.field",
        "profile_id",
        string="Field Lines",
        copy=True,
    )
    model_line_ids = fields.One2many(
        "eh.access.model",
        "profile_id",
        string="Model Lines",
        copy=True,
    )
    node_line_ids = fields.One2many(
        "eh.access.node",
        "profile_id",
        string="Node Lines",
        copy=True,
    )
    chatter_line_ids = fields.One2many(
        "eh.access.chatter",
        "profile_id",
        string="Chatter Lines",
        copy=True,
    )
    domain_line_ids = fields.One2many(
        "eh.access.domain",
        "profile_id",
        string="Domain Rules",
        copy=True,
    )
    hide_chatter = fields.Boolean(
        string="Hide Chatter (everywhere)",
        tracking=True,
        help="Removes the chatter widget from every form view.",
    )
    hide_send_message = fields.Boolean(
        string="Hide 'Send Message'",
        tracking=True,
        help="Hides the Send Message button on every chatter.",
    )
    hide_log_note = fields.Boolean(
        string="Hide 'Log Note'",
        tracking=True,
        help="Hides the Log Note button on every chatter.",
    )
    hide_schedule_activity = fields.Boolean(
        string="Hide 'Schedule Activity'",
        tracking=True,
        help="Hides the Activities button on every chatter.",
    )

    hide_import = fields.Boolean(
        string="Hide Import (everywhere)",
        tracking=True,
        help="Removes the Import button on every list and kanban view.",
    )
    hide_export = fields.Boolean(
        string="Hide Export (everywhere)",
        tracking=True,
        help="Removes the Export button on every list and kanban view.",
    )
    hide_spreadsheet = fields.Boolean(
        string="Hide Insert in Spreadsheet (everywhere)",
        tracking=True,
        help=(
            "Removes 'Insert in Spreadsheet' from list, pivot and graph"
            " cog menus."
        ),
    )
    hide_add_property = fields.Boolean(
        string="Hide Add Property (everywhere)",
        tracking=True,
        help="Removes the 'Add Property' action from form views.",
    )
    disable_debug_mode = fields.Boolean(
        string="Disable Developer Mode",
        tracking=True,
        help=(
            "Strips debug mode from the URL whenever a user in this"
            " profile loads the web client."
        ),
    )
    disable_login = fields.Boolean(
        string="Disable Login",
        tracking=True,
        help=(
            "Users in this profile are denied at the authentication"
            " gate. Use only when the profile is targeted at one user;"
            " applying it to a group disables the whole group."
        ),
    )

    rule_count = fields.Integer(
        compute="_compute_rule_count",
        string="Rules",
        store=False,
    )
    user_count = fields.Integer(
        compute="_compute_user_count",
        string="Users",
        store=False,
    )
    domain_rule_count = fields.Integer(
        compute="_compute_domain_rule_count",
        string="Domain Rules",
        store=False,
    )
    hidden_menu_count = fields.Integer(
        compute="_compute_hidden_menu_count",
        string="Hidden Menus",
        store=False,
    )

    @api.depends("user_ids")
    def _compute_user_count(self):
        for profile in self:
            profile.user_count = len(profile.user_ids)

    @api.depends("domain_line_ids")
    def _compute_domain_rule_count(self):
        for profile in self:
            profile.domain_rule_count = len(profile.domain_line_ids)

    @api.depends("hidden_menu_ids")
    def _compute_hidden_menu_count(self):
        for profile in self:
            profile.hidden_menu_count = len(profile.hidden_menu_ids)

    @api.depends("hidden_menu_ids", "field_line_ids",
                 "model_line_ids", "node_line_ids", "chatter_line_ids",
                 "domain_line_ids",
                 "hide_import", "hide_export", "hide_spreadsheet",
                 "hide_add_property", "disable_debug_mode", "disable_login",
                 "hide_chatter", "readonly")
    def _compute_rule_count(self):
        for profile in self:
            count = (
                len(profile.hidden_menu_ids)
                + len(profile.field_line_ids)
                + len(profile.model_line_ids)
                + len(profile.node_line_ids)
                + len(profile.chatter_line_ids)
                + len(profile.domain_line_ids)
            )
            for flag in (
                profile.hide_import, profile.hide_export,
                profile.hide_spreadsheet, profile.hide_add_property,
                profile.disable_debug_mode, profile.disable_login,
                profile.hide_chatter, profile.readonly,
            ):
                if flag:
                    count += 1
            profile.rule_count = count

    @api.constrains("name")
    def _check_name_unique(self):
        for record in self:
            if not record.name:
                continue
            twin = self.search_count([
                ("name", "=", record.name),
                ("id", "!=", record.id),
            ])
            if twin:
                raise ValidationError(_(
                    "Access Studio: a profile named %(name)s already"
                    " exists. Pick a different name so import / export"
                    " can match by name unambiguously.",
                    name=record.name,
                ))

    @api.constrains("user_ids", "readonly")
    def _check_no_admin_in_readonly(self):
        admin_groups = (
            self.env.ref("base.group_system", raise_if_not_found=False),
            self.env.ref("base.group_erp_manager", raise_if_not_found=False),
        )
        admin_groups = tuple(g for g in admin_groups if g)
        if not admin_groups:
            return
        # res.groups uses `users` on Odoo 18 and earlier, `user_ids`
        # on Odoo 19 and later. Resolve dynamically.
        admin_user_ids = set()
        for group in admin_groups:
            members = getattr(group, "user_ids", None)
            if members is None:
                members = getattr(group, "users", group.browse())
            admin_user_ids.update(members.ids)
        for profile in self:
            if not profile.readonly:
                continue
            for user in profile.user_ids:
                if user.id in admin_user_ids:
                    raise ValidationError(_(
                        "Access Studio: %(user)s is an administrator and"
                        " cannot be placed in a read-only profile.",
                        user=user.display_name,
                    ))

    @api.constrains("date_from", "date_until")
    def _check_date_window(self):
        for profile in self:
            if (profile.date_from and profile.date_until
                    and profile.date_from > profile.date_until):
                raise ValidationError(_(
                    "Access Studio: 'Active From' must not be later than"
                    " 'Active Until'."
                ))

    def action_toggle_active(self):
        for profile in self:
            profile.active = not profile.active
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("eh_access_studio_skip_invalidate"):
            self._invalidate_active_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("eh_access_studio_skip_invalidate"):
            self._invalidate_active_cache()
        return result

    def unlink(self):
        result = super().unlink()
        if not self.env.context.get("eh_access_studio_skip_invalidate"):
            self._invalidate_active_cache()
        return result

    @api.model
    def _invalidate_active_cache(self):
        """Clear ormcaches and signal other workers.

        Implementation note: in Odoo 19, the @tools.ormcache decorator
        does NOT expose a per-method clear_cache. The only way to
        invalidate ormcaches is via Registry.clear_cache(*cache_names)
        which clears entire cache categories. All five of our cached
        methods live in the 'default' category alongside everyone
        else's, so a single registry.clear_cache() call covers ours
        with collateral on third-party defaults. We accept that as the
        platform contract.

        We still beat the alternative pattern (clear_all_caches) which
        nukes every category including 'assets', 'templates', 'routing'
        and 'groups'.

        registry.signal_changes() then notifies other workers in a
        multi-process deployment so they clear their caches at the
        next request.
        """
        try:
            self.env.registry.clear_cache()
        except Exception:
            _logger.exception(
                "Access Studio: registry.clear_cache failed"
            )
        try:
            self.env.registry.signal_changes()
        except Exception:
            _logger.exception(
                "Access Studio: registry.signal_changes failed"
            )

    @api.model
    @tools.ormcache("uid", "cid", "today_iso")
    def _get_active_profile_ids(self, uid, cid, today_iso):
        """Return profile ids active for a user under a given company on
        a specific date.

        Cached on (uid, cid, today_iso). Including the date in the
        cache key lets a profile expire correctly across midnight
        without waiting for a manual cache flush.

        Invalidation happens on profile / line create, write or unlink.
        """
        try:
            domain = [
                ("active", "=", True),
                ("user_ids", "in", uid),
                "|", ("apply_to_all_companies", "=", True),
                ("company_ids", "in", cid),
                "|", ("date_from", "=", False),
                ("date_from", "<=", today_iso),
                "|", ("date_until", "=", False),
                ("date_until", ">=", today_iso),
            ]
            return tuple(self.sudo().search(domain).ids)
        except psycopg2.errors.UndefinedTable:
            # Table not yet created (first install path before our model
            # tables exist). Return empty so callers fall back to
            # default behaviour.
            return ()

    @api.model
    def _today_for_cache_key(self):
        """ISO-format today, used as part of the active-profile cache key."""
        return fields.Date.context_today(self).isoformat()

    @api.model
    @tools.ormcache("uid", "cid", "today_iso", "model_name")
    def _model_line_ids_for(self, uid, cid, today_iso, model_name):
        """Cached lookup of eh.access.model lines for (user, company,
        date, model). Used by base._get_view and base.get_views to
        avoid running a fresh search for every view-render."""
        try:
            profile_ids = self._get_active_profile_ids(uid, cid, today_iso)
            if not profile_ids:
                return ()
            return tuple(self.env["eh.access.model"].sudo().search([
                ("profile_id", "in", list(profile_ids)),
                ("model_name", "=", model_name),
            ]).ids)
        except psycopg2.errors.UndefinedTable:
            return ()

    @api.model
    @tools.ormcache("uid", "cid", "today_iso", "model_name")
    def _chatter_visibility_for(self, uid, cid, today_iso, model_name):
        """Cached chatter visibility flags for the OWL patch RPC.

        Returns a 3-tuple (hide_send, hide_log, hide_schedule). Tuples
        are cheap to cache; the RPC method below converts to a dict
        for the JS contract.
        """
        try:
            profile_ids = self._get_active_profile_ids(uid, cid, today_iso)
            if not profile_ids:
                return (False, False, False)
            profiles = self.sudo().browse(profile_ids)
            per_model_hide = bool(self.env["eh.access.chatter"].sudo().search_count([
                ("profile_id", "in", list(profile_ids)),
                ("model_name", "=", model_name),
            ]))
            global_hide = any(profiles.mapped("hide_chatter")) or per_model_hide
            return (
                global_hide or any(profiles.mapped("hide_send_message")),
                global_hide or any(profiles.mapped("hide_log_note")),
                global_hide or any(profiles.mapped("hide_schedule_activity")),
            )
        except psycopg2.errors.UndefinedTable:
            return (False, False, False)

    def _get_active_profiles_for_current_user(self):
        """Convenience: recordset of active profiles for env.user / env.company."""
        ids = self._get_active_profile_ids(
            self.env.user.id,
            self.env.company.id,
            self._today_for_cache_key(),
        )
        return self.browse(ids)

    @api.model
    def get_chatter_button_visibility(self, model_name):
        """Public RPC: tell the OWL chatter patch which buttons to hide.

        Cached per (uid, cid, today, model_name). The OWL patch calls
        this on every chatter mount; without caching that's one DB
        query per chatter render.
        """
        send, log, schedule = self._chatter_visibility_for(
            self.env.user.id,
            self.env.company.id,
            self._today_for_cache_key(),
            model_name,
        )
        return {
            "hide_send_message": send,
            "hide_log_note": log,
            "hide_schedule_activity": schedule,
        }

    def action_duplicate_profile(self):
        """Copy the profile under a new name and open the copy."""
        self.ensure_one()
        clone = self.copy(default={
            "name": _("%(name)s (copy)", name=self.name),
            "active": False,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "eh.access.profile",
            "view_mode": "form",
            "res_id": clone.id,
            "target": "current",
        }

    def action_diagnostic(self):
        """Render a one-screen summary of what this profile does."""
        self.ensure_one()
        lines = []
        if self.readonly:
            lines.append(_("- Read-only mode: blocks create / edit / delete on every model"))
        if self.hide_chatter:
            lines.append(_("- Chatter hidden on every form view"))
        for flag, label in (
            ("hide_send_message", _("Send Message button hidden")),
            ("hide_log_note", _("Log Note button hidden")),
            ("hide_schedule_activity", _("Activities button hidden")),
            ("hide_import", _("Import button hidden everywhere")),
            ("hide_export", _("Export button hidden everywhere")),
            ("hide_spreadsheet", _("Insert in Spreadsheet hidden everywhere")),
            ("hide_add_property", _("Add Property hidden everywhere")),
            ("disable_login", _("Sign-in disabled for the targeted users")),
            ("disable_debug_mode", _("Developer mode disabled (debug=0 enforced)")),
        ):
            if self[flag]:
                lines.append("- " + label)
        if self.hidden_menu_ids:
            sample = self.hidden_menu_ids[:6]
            tail = "..." if len(self.hidden_menu_ids) > 6 else ""
            lines.append(_(
                "- %(n)s menu(s) hidden: %(names)s%(tail)s",
                n=len(self.hidden_menu_ids),
                names=", ".join(sample.mapped("display_name")),
                tail=tail,
            ))
        if self.field_line_ids:
            lines.append(_(
                "- %(n)s field rule(s) across %(models)s model(s)",
                n=len(self.field_line_ids),
                models=len(self.field_line_ids.mapped("model_id")),
            ))
        if self.model_line_ids:
            lines.append(_(
                "- %(n)s model rule(s) across %(models)s model(s)",
                n=len(self.model_line_ids),
                models=len(self.model_line_ids.mapped("model_id")),
            ))
        if self.node_line_ids:
            lines.append(_(
                "- %(n)s node rule(s) (button / tab / link / filter)",
                n=len(self.node_line_ids),
            ))
        if self.chatter_line_ids:
            lines.append(_(
                "- %(n)s per-model chatter override(s)",
                n=len(self.chatter_line_ids),
            ))
        if self.domain_line_ids:
            lines.append(_(
                "- %(n)s domain rule(s): strict ORM-level gates",
                n=len(self.domain_line_ids),
            ))
        if not lines:
            lines = [_("- No rules configured. The profile is a no-op.")]

        body = _(
            "%(name)s applies to %(users)s user(s) under %(scope)s.\n\n%(body)s",
            name=self.name,
            users=len(self.user_ids),
            scope=_("all companies") if self.apply_to_all_companies
                  else _("%(n)s company / companies", n=len(self.company_ids)),
            body="\n".join(lines),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "info",
                "title": _("Profile summary: %(name)s", name=self.name),
                "message": body,
                "sticky": True,
            },
        }

    def action_test_plan(self):
        """Render a test plan for this profile.

        We deliberately do not impersonate a user from this action.
        Session-level impersonation is risky enough that we want each
        invocation to be an explicit, conscious step (sign in as the
        target user in a private browser window). What we surface here
        is a deterministic, repeatable test plan listing the rules that
        will fire and the users to test as.
        """
        self.ensure_one()
        if not self.user_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "title": _("Test plan not available"),
                    "message": _("Add at least one user to the profile first."),
                    "sticky": False,
                },
            }
        # Display by display_name (not login) to keep PII off-screen
        # where possible. Logins are visible in the User form anyway.
        names = ", ".join(self.user_ids.mapped("display_name"))
        message = _(
            "Sign in as one of %(users)s in a private browser window."
            " The active-profile cache, the ir.rule extension and the"
            " view post-processors all run on every page load, so the"
            " first navigation exercises the full enforcement path.",
            users=names,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "info",
                "title": _("Test plan: %(name)s", name=self.name),
                "message": message,
                "sticky": True,
            },
        }

    @api.model
    def action_health_check(self):
        """Scan the configuration for common issues.

        Surfaces (in order):
          * profiles with no users assigned
          * profiles with no rules and no global toggles
          * profiles whose Active Until date has passed but are still
            active (cron has not yet run, or it failed)
          * domain rules whose stored domain does not parse
        """
        import ast
        warnings = []
        active = self.search([("active", "=", True)])

        no_users = active.filtered(lambda p: not p.user_ids)
        if no_users:
            warnings.append(_(
                "%(n)s active profile(s) have no users assigned: %(names)s",
                n=len(no_users),
                names=", ".join(no_users[:5].mapped("name"))
                + ("..." if len(no_users) > 5 else ""),
            ))

        no_op = active.filtered(lambda p: p.rule_count == 0)
        if no_op:
            warnings.append(_(
                "%(n)s active profile(s) have no rules (no-op):"
                " %(names)s",
                n=len(no_op),
                names=", ".join(no_op[:5].mapped("name"))
                + ("..." if len(no_op) > 5 else ""),
            ))

        today = fields.Date.context_today(self)
        expired = active.filtered(
            lambda p: p.date_until and p.date_until < today,
        )
        if expired:
            warnings.append(_(
                "%(n)s active profile(s) past their Active Until date"
                " (cron has not deactivated them yet): %(names)s",
                n=len(expired),
                names=", ".join(expired[:5].mapped("name"))
                + ("..." if len(expired) > 5 else ""),
            ))

        bad_domains = []
        domain_rules = self.env["eh.access.domain"].sudo().search([
            ("apply_filter", "=", True),
        ])
        for rule in domain_rules:
            if not rule.domain:
                bad_domains.append(rule)
                continue
            try:
                parsed = ast.literal_eval(rule.domain)
                if not isinstance(parsed, list):
                    bad_domains.append(rule)
            except (ValueError, SyntaxError):
                bad_domains.append(rule)
        if bad_domains:
            unique_profile_names = sorted({r.profile_id.name for r in bad_domains})
            warnings.append(_(
                "%(n)s domain rule(s) cannot be parsed and will fail"
                " closed at runtime. Profiles affected: %(names)s",
                n=len(bad_domains),
                names=", ".join(unique_profile_names[:5])
                + ("..." if len(unique_profile_names) > 5 else ""),
            ))

        if not warnings:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "title": _("Access Studio: health check passed"),
                    "message": _(
                        "No issues found across %(n)s active profile(s).",
                        n=len(active),
                    ),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning",
                "title": _("Access Studio: health check"),
                "message": "\n\n".join(warnings),
                "sticky": True,
            },
        }

    @api.model
    def action_conflict_report(self):
        """Detect profiles that contradict each other for the same user.

        We surface the most common operational class of conflict: a
        user is in two active profiles that both target the same model
        on the Domain Access tab with different filters or different
        rights. Returns a sticky notification listing every conflict so
        admins can rationalise their setup.
        """
        Domain = self.env["eh.access.domain"].sudo()
        active = self.search([("active", "=", True)])
        # Build user -> [(profile, domain_line)] mapping
        rows = []
        for profile in active:
            for line in profile.domain_line_ids:
                for user in profile.user_ids:
                    rows.append((user, profile, line))

        by_user_model = {}
        for user, profile, line in rows:
            key = (user.id, line.model_name)
            by_user_model.setdefault(key, []).append((profile, line))

        conflicts = []
        for (user_id, model_name), entries in by_user_model.items():
            if len(entries) < 2:
                continue
            distinct = set()
            for profile, line in entries:
                distinct.add((
                    line.read_right, line.create_right,
                    line.write_right, line.delete_right,
                    line.apply_filter, line.domain or "[]",
                ))
            if len(distinct) > 1:
                user = self.env["res.users"].browse(user_id)
                # Dedupe profile names so a user in three rules across
                # two profiles renders cleanly as 'A, B' rather than
                # 'A, A, B'. The local variable was previously named
                # `_` which shadowed the translation function inside
                # the comprehension; rename to avoid the optical
                # confusion.
                unique_profiles = sorted({
                    profile.name for profile, _line in entries
                })
                names = ", ".join(unique_profiles)
                conflicts.append(_(
                    "%(user)s on %(model)s: %(profiles)s",
                    user=user.display_name,
                    model=model_name,
                    profiles=names,
                ))

        if not conflicts:
            message = _("No domain-rule conflicts detected.")
        else:
            # Cap displayed conflicts so a degenerate setup (hundreds of
            # contradictions) does not produce a wall of text the user
            # cannot read.
            CAP = 25
            shown = conflicts[:CAP]
            extra = len(conflicts) - len(shown)
            tail = (
                _("\n... and %(extra)s more.", extra=extra)
                if extra > 0 else ""
            )
            message = _(
                "%(n)s conflict(s) detected:\n\n%(list)s%(tail)s\n\n"
                "Resolution: deactivate one of the profiles, or align"
                " their domain filters so they describe the same record"
                " set.",
                n=len(conflicts),
                list="\n".join("- " + c for c in shown),
                tail=tail,
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if conflicts else "info",
                "title": _("Conflict report"),
                "message": message,
                "sticky": True,
            },
        }

    @api.model
    def _cron_deactivate_expired_profiles(self):
        """Deactivate profiles whose Active Until has passed.

        Per-record savepoint keeps a single bad row from blocking the
        whole batch (engineering rule 5). The cache is invalidated once
        at the end rather than once per profile so a thousand-row
        cleanup does not fire a thousand registry signals.
        """
        today = fields.Date.context_today(self)
        expired = self.search([
            ("active", "=", True),
            ("date_until", "!=", False),
            ("date_until", "<", today),
        ])
        if not expired:
            return True
        deactivated = 0
        for profile in expired:
            with self.env.cr.savepoint():
                # Skip the per-row invalidation by writing in a context
                # that the line mixin and our own write hooks honour.
                # We fall back to a single invalidate call below.
                profile.with_context(eh_access_studio_skip_invalidate=True).active = False
                profile.with_context(eh_access_studio_skip_invalidate=True).message_post(
                    body=_(
                        "Access Studio: profile auto-deactivated because"
                        " its Active Until date (%(date)s) has passed.",
                        date=profile.date_until,
                    ),
                )
                deactivated += 1
        # One bulk invalidation at the end.
        self._invalidate_active_cache()
        _logger.info(
            "Access Studio: cron deactivated %s expired profile(s).",
            deactivated,
        )
        return True
