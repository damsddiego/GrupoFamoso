# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: per-model record-rule overlay.

A domain rule attaches to a profile and a model and answers four
questions for users in that profile:

  * read_right    can the user read records of this model?
  * create_right  can the user create new records?
  * write_right   can the user edit existing records?
  * delete_right  can the user delete records?

When `apply_filter` is enabled, the `domain` field narrows the set of
records to which read / write / delete apply. The domain may include
smart placeholder sentinels that are resolved at evaluation time:

  __uid__              current user id
  __cid__              current company id
  __company_ids__      list of allowed company ids
  __today__            today (date)
  __week_start__ ...   plus the full date sentinel set documented in
                       tools/domain_resolver.py.

Resolution is delegated to tools.domain_resolver, which is a plain
Python module testable without Odoo loaded.

Audit log: every blocked operation posts a message on the responsible
profile via mail.thread, recording the user, model, mode and (when
known) the record display name.
"""
import ast
import logging

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class EhAccessDomain(models.Model):
    _name = "eh.access.domain"
    _inherit = ["eh.access.line.mixin"]
    _description = "User Access Studio Domain Rule"
    _order = "model_name, id"

    profile_id = fields.Many2one(
        "eh.access.profile",
        string="Profile",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        index=True,
    )

    read_right = fields.Boolean(string="Read", default=True)
    create_right = fields.Boolean(string="Create")
    write_right = fields.Boolean(string="Edit")
    delete_right = fields.Boolean(string="Delete")

    rights_preset = fields.Selection(
        [
            ("read_only", "Read only"),
            ("read_create", "Read + Create"),
            ("read_write", "Read + Edit"),
            ("read_create_write", "Read + Create + Edit"),
            ("full", "Full access (Read + Create + Edit + Delete)"),
            ("none", "No access"),
            ("custom", "Custom"),
        ],
        string="Access level",
        compute="_compute_rights_preset",
        inverse="_inverse_rights_preset",
        store=True,
        help=(
            "Pick a common combination. Switch to 'Custom' to set"
            " individual rights checkboxes."
        ),
    )

    @api.depends("read_right", "create_right", "write_right", "delete_right")
    def _compute_rights_preset(self):
        # Map (read, create, write, delete) tuples to preset names.
        presets = {
            (False, False, False, False): "none",
            (True, False, False, False): "read_only",
            (True, True, False, False): "read_create",
            (True, False, True, False): "read_write",
            (True, True, True, False): "read_create_write",
            (True, True, True, True): "full",
        }
        for record in self:
            key = (
                record.read_right,
                record.create_right,
                record.write_right,
                record.delete_right,
            )
            record.rights_preset = presets.get(key, "custom")

    def _inverse_rights_preset(self):
        mapping = {
            "none": (False, False, False, False),
            "read_only": (True, False, False, False),
            "read_create": (True, True, False, False),
            "read_write": (True, False, True, False),
            "read_create_write": (True, True, True, False),
            "full": (True, True, True, True),
        }
        for record in self:
            if record.rights_preset == "custom" or not record.rights_preset:
                continue
            r, c, w, d = mapping[record.rights_preset]
            record.write({
                "read_right": r,
                "create_right": c,
                "write_right": w,
                "delete_right": d,
            })

    apply_filter = fields.Boolean(
        string="Apply Filter",
        help=(
            "When enabled, the rule limits the set of records to which"
            " the chosen rights apply. Without a filter, the rights"
            " apply to all records of the model."
        ),
    )
    domain = fields.Text(
        string="Filter",
        default="[]",
        help=(
            "Python list of domain leaves. Smart placeholders are"
            " supported. Example: [(\"company_id\", \"in\","
            " \"__company_ids__\"), (\"create_date\", \">=\","
            " \"__month_start__\")]."
        ),
    )

    @api.constrains("domain", "apply_filter")
    def _check_domain_parses(self):
        for record in self:
            if not record.apply_filter:
                continue
            try:
                parsed = ast.literal_eval(record.domain or "[]")
            except (ValueError, SyntaxError) as err:
                raise ValidationError(_(
                    "Access Studio: filter cannot be parsed (%(error)s)."
                    " Use a Python list of domain leaves.",
                    error=err,
                ))
            if not isinstance(parsed, list):
                raise ValidationError(_(
                    "Access Studio: filter must be a Python list."
                ))

    # Sentinel returned by _resolved_domain when the rule is meant to
    # apply but the stored domain cannot be parsed. The ir.rule
    # extension treats this as "block all records" so a misconfiguration
    # fails closed instead of silently granting access.
    _BLOCK_ALL_DOMAIN = [("id", "=", False)]

    def _resolved_domain(self, today=None):
        """Return the domain with placeholder sentinels resolved.

        Return-value contract:
          * apply_filter is False: return [] (no narrowing)
          * apply_filter is True, parse succeeds: resolved domain
          * apply_filter is True, parse fails: BLOCK_ALL (fail closed)
        """
        from odoo.addons.eh_access_studio.tools import domain_resolver
        if not self.apply_filter:
            return []
        if not self.domain:
            # apply_filter on but no domain stored: configuration error,
            # fail closed.
            _logger.warning(
                "Access Studio: rule %s has apply_filter on but no"
                " domain. Blocking access.", self.id,
            )
            return list(self._BLOCK_ALL_DOMAIN)
        try:
            raw = ast.literal_eval(self.domain)
        except (ValueError, SyntaxError):
            _logger.exception(
                "Access Studio: invalid domain on rule %s, blocking"
                " access (fail closed).", self.id,
            )
            return list(self._BLOCK_ALL_DOMAIN)
        if not isinstance(raw, list):
            _logger.warning(
                "Access Studio: rule %s domain is not a list (got %s),"
                " blocking access.", self.id, type(raw).__name__,
            )
            return list(self._BLOCK_ALL_DOMAIN)
        ctx = {
            "uid": self.env.user.id,
            "cid": self.env.company.id,
            "company_ids": self.env.companies.ids,
            "today": today or fields.Date.context_today(self),
        }
        try:
            return domain_resolver.resolve(raw, ctx)
        except Exception:
            _logger.exception(
                "Access Studio: domain resolver failed on rule %s,"
                " blocking access.", self.id,
            )
            return list(self._BLOCK_ALL_DOMAIN)
