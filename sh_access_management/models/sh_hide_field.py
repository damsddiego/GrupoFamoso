# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import html_escape


class ShFieldAccess(models.Model):
    """
        A class to manage the access of fields.
    """
    _name = "sh.field.access"
    _description = "Field Access"
    _inherit = ['mail.thread']

    name = fields.Char(tracking=True)
    model_id = fields.Many2one('ir.model', string="Model", tracking=True)
    field_ids = fields.Many2many(
        'ir.model.fields',
        string="Fields",
        domain="[('model_id', '=', model_id)]",
        tracking=True
    )
    readonly = fields.Boolean(tracking=True)
    required = fields.Boolean(tracking=True)
    invisible = fields.Boolean(tracking=True)
    sh_hide_external_links = fields.Boolean("External Links", tracking=True)
    sh_hide_create_edit = fields.Boolean("Hide Create and Edit", tracking=True)
    access_manager_id = fields.Many2one(
        "sh.access.manager", string="Access Manager", tracking=True)

    def write(self, vals):
        """
        A method to write values.
        """
        if self._context.get('disable_child_tracking_forward'):
            return super().write(vals)
        tracked_fields = [
            f for f in vals
            if f in self._fields and getattr(self._fields[f], 'tracking', False)
        ]
        initial_values = {
            rec.id: {f: rec[f] for f in tracked_fields}
            for rec in self
        }

        res = super().write(vals)
        tracking_data = self._message_track(tracked_fields, initial_values)

        for rec in self:
            if rec.access_manager_id and rec.id in tracking_data:
                _, tracking_value_ids = tracking_data[rec.id]
                if tracking_value_ids:
                    field = self.env['ir.model.fields'].search([
                        ('model', '=', rec.access_manager_id._name),
                        ('relation', '=', rec._name),
                        ('ttype', '=', 'one2many')
                    ], limit=1)

                    parent_field_label = field.field_description or rec._name
                    display_label = html_escape(str(rec.id) or rec.name or rec.display_name) \
                        if rec.display_name else str(rec.id)

                    msg = Markup(
                        "<b>Update from One2many field: %s — Id: %s</b>") % \
                        (parent_field_label, display_label)

                    rec.access_manager_id.with_context(
                        disable_child_tracking_forward=True).message_post(
                        body=msg,
                        tracking_value_ids=tracking_value_ids,
                        subtype_xmlid='mail.mt_note'
                    )

        return res
