# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import fields, models, api
from lxml import etree
from markupsafe import Markup
from odoo.tools import html_escape


class ShFilterAccess(models.Model):
    _name = "sh.filter.access"
    _description = "Filter Access"
    _inherit = ['mail.thread']

    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        required=True,
        ondelete="cascade",
        tracking=True
    )

    access_manager_id = fields.Many2one(
        "sh.access.manager", 
        string="Access Manager", 
        tracking=True
    )

    sh_store_filter_data_ids = fields.Many2many(
        'sh.store.model.data',
        'sh_filter_hide_view_nodes_store_model_nodes_rel',
        'sh_hide_id', 'sh_store_id',
        string='Hide Filters',
        domain="[('model_id','=',model_id),('sh_node_option','=','filter')]",
        tracking=True
    )

    sh_store_groupby_data_ids = fields.Many2many(
        'sh.store.model.data',
        'sh_groupby_hide_view_nodes_store_model_nodes_rel',
        'sh_hide_id', 'sh_store_id',
        string='Hide Group By',
        domain="[('model_id','=',model_id),('sh_node_option','=','groupby')]",
        tracking=True
    )


    @api.model
    @api.onchange('model_id')
    def _get_filters_groupby(self):
        store_model_nodes_obj = self.env['sh.store.model.data']
        view_obj = self.env['ir.ui.view']

        if self.model_id:
            views = view_obj.search([
                ('model', '=', self.model_id.model),
                ('type', '=', 'search'),
            ])
            
            for view in views:
                res = self.env[self.model_id.model].sudo().get_view(view_id=view.id, view_type='search')
                doc = etree.XML(res['arch'])
                
                # Find regular filters
                filter_nodes = doc.xpath("//filter[not(parent::group)]")
                filter_nodes2 = doc.xpath("//group[@string='Filters']//filter")
                filter_nodes.extend(filter_nodes2) 
                
                for node in filter_nodes:
                    filter_name = node.get('name')
                    filter_string = node.get('string')
                    if filter_name and filter_string:
                        domain = [
                            ('model_id', '=', self.model_id.id),
                            ('sh_node_option', '=', 'filter'),
                            ('sh_attribute_name', '=', filter_name),
                            ('sh_attribute_string', '=', filter_string)
                        ]
                        if not store_model_nodes_obj.search(domain):
                            store_model_nodes_obj.create({
                                'model_id': self.model_id.id,
                                'sh_node_option': 'filter',
                                'sh_attribute_name': filter_name,
                                'sh_attribute_string': filter_string
                            })
                
                # Find group_by options inside <group>
                groupby_nodes = doc.xpath("//group/filter")
                groupby_nodes = [node for node in groupby_nodes if node not in filter_nodes2]
                for node in groupby_nodes:
                    groupby_name = node.get('name')
                    groupby_string = node.get('string')
                    if groupby_name and groupby_string:
                        domain = [
                            ('model_id', '=', self.model_id.id),
                            ('sh_node_option', '=', 'groupby'),
                            ('sh_attribute_name', '=', groupby_name),
                            ('sh_attribute_string', '=', groupby_string)
                        ]
                        if not store_model_nodes_obj.search(domain):
                            store_model_nodes_obj.create({
                                'model_id': self.model_id.id,
                                'sh_node_option': 'groupby',
                                'sh_attribute_name': groupby_name,
                                'sh_attribute_string': groupby_string
                            })

    def write(self, vals):
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
                    display_label = html_escape(str(rec.id) or rec.name or rec.display_name) if rec.display_name else str(rec.id)

                    msg = Markup("<b>Update from One2many field: %s — Id: %s</b>") % (parent_field_label, display_label)

                    rec.access_manager_id.with_context(disable_child_tracking_forward=True).message_post(
                        body=msg,
                        tracking_value_ids=tracking_value_ids,
                        subtype_xmlid='mail.mt_note'
                    )
    
        return res