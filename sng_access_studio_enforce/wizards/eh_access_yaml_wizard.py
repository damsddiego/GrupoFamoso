# -*- coding: utf-8 -*-
"""Lleva el flag enforce_server en el YAML de exportación/importación."""
from odoo import models


class EhAccessYamlWizard(models.TransientModel):
    _inherit = "eh.access.yaml.wizard"

    def _serialise_profile(self, profile):
        data = super()._serialise_profile(profile)
        by_key = {
            (line.model_name, line.kind, line.target_name): line.enforce_server
            for line in profile.node_line_ids
        }
        for raw in data.get("node_lines", []):
            key = (raw.get("model"), raw.get("kind"), raw.get("target_name"))
            raw["enforce_server"] = bool(by_key.get(key))
        return data

    def _node_line_payload(self, raw, Model, Field):
        command = super()._node_line_payload(raw, Model, Field)
        if command:
            command[2]["enforce_server"] = bool(raw.get("enforce_server"))
        return command
