# -*- coding: utf-8 -*-
# Copyright 2026 ERP Heritage (https://www.erpheritage.com.au)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
User Access Studio: YAML import / export wizard.

The wizard serialises and deserialises the configuration of one or more
profiles in a portable, human-readable format. Useful for:
  * version-controlling the access configuration alongside the rest of
    the deployment
  * promoting profiles from staging to production without database
    surgery
  * sharing a baseline profile across customer instances
"""
import base64
import logging
from io import StringIO

import yaml

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Field families serialised per profile. Pure-Python types only so the
# YAML round-trips cleanly.
PROFILE_SCALAR_FIELDS = (
    "name", "sequence", "active", "readonly",
    "apply_to_all_companies",
    "date_from", "date_until",
    "hide_chatter", "hide_send_message", "hide_log_note",
    "hide_schedule_activity",
    "hide_import", "hide_export", "hide_spreadsheet",
    "hide_add_property",
    "disable_login", "disable_debug_mode",
)


class EhAccessYamlWizard(models.TransientModel):
    _name = "eh.access.yaml.wizard"
    _description = "User Access Studio Import / Export"

    mode = fields.Selection(
        [("export", "Export"), ("import", "Import")],
        required=True,
        default="export",
    )
    profile_ids = fields.Many2many(
        "eh.access.profile",
        string="Profiles to export",
    )
    payload = fields.Binary(
        string="YAML",
        attachment=False,
        help=(
            "Export: filled in when the export action runs. Import:"
            " upload the file you want to import."
        ),
    )
    payload_name = fields.Char(string="File name", default="eh_access_profiles.yaml")
    summary = fields.Text(string="Result", readonly=True)

    def action_export(self):
        self.ensure_one()
        profiles = self.profile_ids
        if not profiles:
            raise UserError(_("Pick at least one profile to export."))
        data = [self._serialise_profile(p) for p in profiles]
        text = yaml.safe_dump(
            {"profiles": data},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        self.write({
            "payload": base64.b64encode(text.encode("utf-8")),
            "summary": _(
                "Serialised %(count)s profile(s).",
                count=len(profiles),
            ),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_import(self):
        self.ensure_one()
        if not self.payload:
            raise UserError(_("Upload a YAML file first."))
        # Cap payload size to keep the import path memory-safe. 1 MB of
        # YAML covers tens of thousands of rule lines comfortably.
        max_bytes = 1024 * 1024
        if isinstance(self.payload, bytes) and len(self.payload) > max_bytes:
            raise UserError(_(
                "YAML payload too large (max %(mb)s MB). Split the"
                " export into smaller files.",
                mb=max_bytes // (1024 * 1024),
            ))
        try:
            decoded = base64.b64decode(self.payload)
        except (ValueError) as err:
            raise UserError(_(
                "Could not decode the uploaded file (%(error)s)."
                " Expected base64.",
                error=err,
            )) from err
        if len(decoded) > max_bytes:
            raise UserError(_(
                "YAML payload too large after decode (max"
                " %(mb)s MB).",
                mb=max_bytes // (1024 * 1024),
            ))
        try:
            text = decoded.decode("utf-8")
        except UnicodeDecodeError as err:
            raise UserError(_(
                "Could not decode the uploaded file (%(error)s)."
                " Expected UTF-8.",
                error=err,
            )) from err
        try:
            parsed = yaml.safe_load(StringIO(text))
        except yaml.YAMLError as err:
            raise UserError(_(
                "Could not parse YAML (%(error)s).",
                error=err,
            )) from err
        if not isinstance(parsed, dict) or "profiles" not in parsed:
            raise UserError(_(
                "YAML root must be a mapping with a 'profiles' key."
            ))
        profiles_payload = parsed["profiles"] or []
        if not isinstance(profiles_payload, list):
            raise UserError(_(
                "'profiles' must be a list."
            ))
        created = updated = 0
        for entry in profiles_payload:
            if not isinstance(entry, dict):
                continue
            with self.env.cr.savepoint():
                if self._upsert_profile(entry):
                    updated += 1
                else:
                    created += 1
        self.write({
            "summary": _(
                "Imported: %(created)s created, %(updated)s updated.",
                created=created,
                updated=updated,
            ),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # -- helpers ----------------------------------------------------------

    def _serialise_profile(self, profile):
        data = {f: profile[f] for f in PROFILE_SCALAR_FIELDS}
        # Date fields serialise to plain ISO strings.
        for key in ("date_from", "date_until"):
            if data.get(key):
                data[key] = data[key].isoformat()
        # Filter out empty values so sorted() never compares None with
        # str (Python 3 raises TypeError on mixed-type sort).
        data["users"] = sorted(login for login in profile.user_ids.mapped("login") if login)
        data["companies"] = sorted(name for name in profile.company_ids.mapped("name") if name)
        data["hidden_menus"] = sorted(
            label for label in profile.hidden_menu_ids.mapped(lambda m: m.complete_name or m.name)
            if label
        )
        data["field_lines"] = [
            {
                "model": line.model_name,
                "fields": sorted(line.field_ids.mapped("name")),
                "invisible": line.invisible,
                "readonly": line.readonly,
                "required": line.required,
            }
            for line in profile.field_line_ids
        ]
        data["model_lines"] = [
            {
                "model": line.model_name,
                **{
                    f: line[f]
                    for f in (
                        "restrict_create", "restrict_edit", "restrict_delete",
                        "restrict_archive", "restrict_duplicate",
                        "restrict_import", "restrict_export",
                        "restrict_spreadsheet", "restrict_add_property",
                    )
                },
                "hidden_view_types": line.hidden_view_types,
                "hidden_reports": sorted(
                    line.hidden_report_action_ids.mapped("xml_id"),
                ),
                "hidden_server_actions": sorted(
                    line.hidden_server_action_ids.mapped("xml_id"),
                ),
            }
            for line in profile.model_line_ids
        ]
        data["node_lines"] = [
            {
                "model": line.model_name,
                "kind": line.kind,
                "target_name": line.target_name,
                "target_label": line.target_label or "",
            }
            for line in profile.node_line_ids
        ]
        data["chatter_lines"] = sorted(profile.chatter_line_ids.mapped("model_name"))
        data["domain_lines"] = [
            {
                "model": line.model_name,
                "read_right": line.read_right,
                "create_right": line.create_right,
                "write_right": line.write_right,
                "delete_right": line.delete_right,
                "apply_filter": line.apply_filter,
                "domain": line.domain or "[]",
            }
            for line in profile.domain_line_ids
        ]
        return data

    def _upsert_profile(self, entry):
        Profile = self.env["eh.access.profile"]
        Model = self.env["ir.model"]
        Field = self.env["ir.model.fields"]
        User = self.env["res.users"]
        Menu = self.env["ir.ui.menu"]
        existing = Profile.search([("name", "=", entry.get("name"))], limit=1)
        vals = {f: entry[f] for f in PROFILE_SCALAR_FIELDS if f in entry}
        if entry.get("users"):
            user_ids = User.search([("login", "in", entry["users"])]).ids
            vals["user_ids"] = [(6, 0, user_ids)]
        if entry.get("companies"):
            companies = self.env["res.company"].search([
                ("name", "in", entry["companies"]),
            ]).ids
            vals["company_ids"] = [(6, 0, companies)]
        if entry.get("hidden_menus") is not None:
            menu_ids = []
            for label in entry["hidden_menus"]:
                menu = Menu.search([("complete_name", "=", label)], limit=1)
                if not menu:
                    menu = Menu.search([("name", "=", label)], limit=1)
                if menu:
                    menu_ids.append(menu.id)
            vals["hidden_menu_ids"] = [(6, 0, menu_ids)]

        # Replace child collections each import to keep the file the
        # source of truth. Use ondelete-cascade-friendly semantics.
        line_specs = (
            ("field_line_ids", "field_lines", self._field_line_payload),
            ("model_line_ids", "model_lines", self._model_line_payload),
            ("node_line_ids", "node_lines", self._node_line_payload),
            ("chatter_line_ids", "chatter_lines", self._chatter_line_payload),
            ("domain_line_ids", "domain_lines", self._domain_line_payload),
        )
        for field, key, builder in line_specs:
            if key not in entry:
                continue
            commands = [(5, 0, 0)]
            for raw in entry[key] or []:
                command = builder(raw, Model, Field)
                if command:
                    commands.append(command)
            vals[field] = commands

        if existing:
            existing.write(vals)
            return True
        Profile.create(vals)
        return False

    @staticmethod
    def _resolve_model(Model, name):
        if not name:
            return None
        rec = Model.search([("model", "=", name)], limit=1)
        if not rec:
            _logger.warning(
                "Access Studio YAML import: model %s not found in this"
                " database; skipping the rule line that references it.",
                name,
            )
            return None
        return rec

    def _field_line_payload(self, raw, Model, Field):
        model = self._resolve_model(Model, raw.get("model"))
        if not model:
            return None
        field_names = raw.get("fields") or []
        field_ids = Field.search([
            ("model_id", "=", model.id),
            ("name", "in", field_names),
        ]).ids
        return (0, 0, {
            "model_id": model.id,
            "field_ids": [(6, 0, field_ids)],
            "invisible": bool(raw.get("invisible")),
            "readonly": bool(raw.get("readonly")),
            "required": bool(raw.get("required")),
        })

    def _model_line_payload(self, raw, Model, Field):
        model = self._resolve_model(Model, raw.get("model"))
        if not model:
            return None
        return (0, 0, {
            "model_id": model.id,
            "restrict_create": bool(raw.get("restrict_create")),
            "restrict_edit": bool(raw.get("restrict_edit")),
            "restrict_delete": bool(raw.get("restrict_delete")),
            "restrict_archive": bool(raw.get("restrict_archive")),
            "restrict_duplicate": bool(raw.get("restrict_duplicate")),
            "restrict_import": bool(raw.get("restrict_import")),
            "restrict_export": bool(raw.get("restrict_export")),
            "restrict_spreadsheet": bool(raw.get("restrict_spreadsheet")),
            "restrict_add_property": bool(raw.get("restrict_add_property")),
            "hidden_view_types": raw.get("hidden_view_types") or "",
        })

    def _node_line_payload(self, raw, Model, Field):
        model = self._resolve_model(Model, raw.get("model"))
        if not model or not raw.get("target_name"):
            return None
        return (0, 0, {
            "model_id": model.id,
            "kind": raw.get("kind") or "button",
            "target_name": raw["target_name"],
            "target_label": raw.get("target_label") or "",
        })

    def _chatter_line_payload(self, raw, Model, Field):
        # raw can be a string (model name) for backwards-compat with the
        # serialiser shape.
        name = raw if isinstance(raw, str) else raw.get("model")
        model = self._resolve_model(Model, name)
        if not model:
            return None
        return (0, 0, {"model_id": model.id})

    def _domain_line_payload(self, raw, Model, Field):
        model = self._resolve_model(Model, raw.get("model"))
        if not model:
            return None
        return (0, 0, {
            "model_id": model.id,
            "read_right": bool(raw.get("read_right", True)),
            "create_right": bool(raw.get("create_right")),
            "write_right": bool(raw.get("write_right")),
            "delete_right": bool(raw.get("delete_right")),
            "apply_filter": bool(raw.get("apply_filter")),
            "domain": raw.get("domain") or "[]",
        })
