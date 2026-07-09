# -*- coding: utf-8 -*-

from odoo import api, models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'sng.audit.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            fields_to_log = record._audit_fields_from_vals(vals)
            new_values = record._audit_snapshot(fields_to_log)
            if not new_values:
                continue
            record._audit_log(
                'create',
                new_values=new_values,
            )
        return records

    def write(self, vals):
        fields_to_log = self._audit_fields_from_vals(vals)
        if not fields_to_log:
            return super().write(vals)
        old_values_by_id = {
            record.id: record._audit_snapshot(fields_to_log)
            for record in self
        }
        result = super().write(vals)
        for record in self:
            new_values = record._audit_snapshot(fields_to_log)
            if not old_values_by_id.get(record.id) and not new_values:
                continue
            record._audit_log(
                'write',
                old_values=old_values_by_id.get(record.id),
                new_values=new_values,
            )
        return result

    def unlink(self):
        for record in self:
            record._audit_log(
                'unlink',
                old_values=record._audit_snapshot(),
            )
        return super().unlink()
