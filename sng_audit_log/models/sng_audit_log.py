# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SngAuditLog(models.Model):
    _name = 'sng.audit.log'
    _description = 'SNG Audit Log'
    _order = 'event_date desc, id desc'

    name = fields.Char(string='Description', required=True)
    event_date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    action = fields.Selection(
        [
            ('create', 'Create'),
            ('write', 'Update'),
            ('unlink', 'Delete'),
        ],
        string='Action',
        required=True,
        index=True,
    )
    model_name = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    record_name = fields.Char(string='Record Name')
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        index=True,
        ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        ondelete='set null',
    )
    old_values = fields.Text(string='Old Values')
    new_values = fields.Text(string='New Values')
    changed_fields = fields.Char(string='Changed Fields')

    @api.model
    def _json_dumps(self, values):
        return json.dumps(values or {}, ensure_ascii=False, sort_keys=True)

    @api.model
    def _field_to_audit_value(self, record, field_name):
        field = record._fields.get(field_name)
        if not field:
            return False

        value = record[field_name]
        if field.type == 'many2one':
            return value and {
                'id': value.id,
                'display_name': value.display_name,
            } or False
        if field.type in ('one2many', 'many2many'):
            return [
                {'id': item.id, 'display_name': item.display_name}
                for item in value
            ]
        if field.type in ('date', 'datetime'):
            return value and fields.Datetime.to_string(value) or False
        if field.type == 'binary':
            return value and '<binary>' or False
        return value

    @api.model
    def _snapshot(self, record, field_names=None):
        if not record:
            return {}

        if field_names is None:
            field_names = record._fields.keys()

        ignored_fields = {
            '__last_update',
            'activity_ids',
            'activity_state',
            'message_ids',
            'message_follower_ids',
        }
        values = {}
        for field_name in field_names:
            if field_name in ignored_fields:
                continue
            field = record._fields.get(field_name)
            if not field or field.compute and not field.store:
                continue
            try:
                values[field_name] = self._field_to_audit_value(
                    record,
                    field_name,
                )
            except Exception:
                values[field_name] = '<unavailable>'
        return values

    @api.model
    def _record_company(self, record):
        company = getattr(record, 'company_id', False)
        return company.id if company else self.env.company.id

    @api.model
    def log_record(self, record, action, old_values=None, new_values=None):
        try:
            record_name = record.display_name
            description = '%s %s %s' % (
                action.upper(),
                record._name,
                record_name,
            )
            return self.sudo().create({
                'name': description[:255],
                'action': action,
                'model_name': record._name,
                'res_id': record.id,
                'record_name': record_name,
                'user_id': self.env.uid,
                'company_id': self._record_company(record),
                'old_values': self._json_dumps(old_values),
                'new_values': self._json_dumps(new_values),
                'changed_fields': ', '.join(sorted(
                    set((old_values or {}).keys()) |
                    set((new_values or {}).keys())
                )),
            })
        except Exception:
            _logger.exception(
                'Could not create audit log for %s,%s',
                record._name,
                record.id,
            )
            return False


class SngAuditMixin(models.AbstractModel):
    _name = 'sng.audit.mixin'
    _description = 'SNG Audit Mixin'

    @api.model
    def _audit_fields_from_vals(self, vals):
        return [
            field_name
            for field_name in vals
            if field_name in self._fields and field_name != 'write_date'
        ]

    def _audit_snapshot(self, field_names=None):
        return self.env['sng.audit.log']._snapshot(self, field_names)

    def _audit_log(self, action, old_values=None, new_values=None):
        return self.env['sng.audit.log'].log_record(
            self,
            action,
            old_values=old_values,
            new_values=new_values,
        )
