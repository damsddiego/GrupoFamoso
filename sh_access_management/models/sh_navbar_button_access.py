# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields,models,api,_
import re
from lxml import etree, html
from markupsafe import Markup
from odoo.tools import html_escape


class hide_view_nodes(models.Model):
    _name = 'sh.navbar.buttons.access'
    _description = 'Hide Navbar And Buttos'
    _inherit = ['mail.thread']

    model_id = fields.Many2one(
        'ir.model', string='Model', index=True, required=True, ondelete='cascade', tracking=True)

    model_name = fields.Char(
        string='Model Name', related='model_id.model', readonly=True, store=True, tracking=True)

    sh_store_btn_data_ids = fields.Many2many(
        'sh.store.model.data',
        'sh_btn_hide_view_nodes_store_model_nodes_rel',
        'sh_hide_id', 'sh_store_id',
        string='Hide Button',
        domain="[('sh_node_option','=','button')]",
        tracking=True)

    sh_store_page_data_ids = fields.Many2many(
        'sh.store.model.data',
        'sh_page_hide_view_nodes_store_model_nodes_rel',
        'sh_hide_id', 'sh_store_id',
        string='Hide Tab/Page',
        domain="[('sh_node_option','=','page')]",
        tracking=True)
    
    sh_store_kanban_link_ids = fields.Many2many(
        'sh.store.model.data',
        'sh_kanban_link_hide_view_nodes_store_model_nodes_rel',
        'sh_hide_id', 'sh_store_id',
        string='Hide Kanban Link',
        domain="[('model_id','=',model_id),('sh_node_option','=','link')]",
        tracking=True
    )

    access_manager_id = fields.Many2one(
        'sh.access.manager', string='Access Management', tracking=True)

    def _store_btn_data(self,btn, smart_button=False,smart_button_string=False):
        # string_value is used in case of kanban view button store, 
        string_value = 'string_value' in self._context.keys() and self._context['string_value'] or False
        
        store_model_button_obj = self.env['sh.store.model.data']
        name = btn.get('string') or string_value
        if smart_button:
            name = smart_button_string + ' - (Smart Button)'
        store_model_button_obj.create({
                'model_id' : self.model_id.id,
                'sh_node_option' : 'button',
                'sh_attribute_name' : btn.get('name'),
                'sh_attribute_string' : name,
                'sh_button_type' : btn.get('type'),
                'sh_is_smart_button' : smart_button,
            })
       

    def _get_smart_btn_string(self,btn_list,type=False):
        store_model_button_obj = self.env['sh.store.model.data']
        def _get_span_text(span_list):
            name = ''
            for sp in span_list:
                if sp.text:
                    name = name  +' '+ sp.text
            name = name.strip()
            return name    

        for btn in btn_list:
            name = ''
            field_list = btn.findall('field')
            if field_list:
                name = field_list[0].get('string')
            else:
                span_list = btn.findall('span')
                if span_list:
                    name = _get_span_text(span_list)
                else:
                    div_list = btn.findall('div')
                    if div_list:
                        span_list = div_list[0].findall('span')
                        if span_list:
                            name = _get_span_text(span_list)
            if not name:
                try:
                    name = btn.get('string')
                except:
                    pass
            if name and (type == 'object' or type == 'action'):
                # Use robust domain check
                domain = [
                    ('model_id', '=', self.model_id.id),
                    ('sh_attribute_name', '=', btn.get('name')),
                ]
                smart_button_id = store_model_button_obj.search(domain, limit=1)
                if not smart_button_id:
                    self._store_btn_data(btn,smart_button=True,smart_button_string=name)
                else:
                    smart_button_id[0].sh_is_smart_button = True


    
    @api.model
    @api.onchange('model_id')
    def _get_button(self):
        store_model_nodes_obj = self.env['sh.store.model.data']

        if self.model_id and self.model_name:
            view_list = ['form', 'list', 'kanban']
            for view_type in view_list:
                try:
                    res = self.env[self.model_name].sudo().get_view(view_type=view_type)
                    doc = etree.XML(res['arch'])
                except Exception:
                    continue

                if view_type == 'form':
                    header = doc.find('header')
                    if header is not None:
                        header_buttons = header.xpath("./button[@type='object' or @type='action']")
                        for btn in header_buttons:
                            name_attr = btn.get('name')
                            string_attr = btn.get('string') or ''.join(btn.itertext()).strip()
                            if name_attr and string_attr:
                                domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name_attr)]
                                if not store_model_nodes_obj.search(domain, limit=1):
                                    store_model_nodes_obj.create({
                                        'model_id' : self.model_id.id,
                                        'sh_node_option' : 'button',
                                        'sh_attribute_name' : name_attr,
                                        'sh_attribute_string' : string_attr,
                                        'sh_button_type' : btn.get('type'),
                                        'sh_is_smart_button' : False,
                                    })
                
                object_link = doc.xpath("//a")
                for btn in object_link:
                    name_attr = btn.get('name')
                    if btn.text and '\n' not in btn.text and 'type' in btn.attrib.keys() and name_attr:
                        domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name_attr)]
                        if not store_model_nodes_obj.search(domain, limit=1):
                            store_model_nodes_obj.create({
                                'model_id' : self.model_id.id,
                                'sh_node_option' : 'link',
                                'sh_attribute_name' : name_attr,
                                'sh_attribute_string' : btn.text,
                                'sh_button_type' : btn.get('type'),
                            })

                object_button = doc.xpath("//button[@type='object']")
                for btn in object_button:
                    name_attr = btn.get('name')
                    string_value = btn.get('string')
                    if view_type == 'kanban' and not string_value:
                        try:
                            string_value = btn.text if not btn.text.startswith('\n') else False
                        except:
                            pass
                    if name_attr and string_value:
                        domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name_attr)]
                        if not store_model_nodes_obj.search(domain, limit=1):
                            self.with_context(string_value=string_value)._store_btn_data(btn)

                action_button = doc.xpath("//button[@type='action']")
                for btn in action_button:
                    name_attr = btn.get('name')
                    string_value = btn.get('string')
                    if view_type == 'kanban' and not string_value:
                        try:
                            string_value = btn.text if not btn.text.startswith('\n') else False
                        except:
                            pass
                    if name_attr and string_value:
                        domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name_attr)]
                        if not store_model_nodes_obj.search(domain, limit=1):
                            self.with_context(string_value=string_value)._store_btn_data(btn)

                if view_type == 'kanban':
                    arch_raw = res.get('arch', '')
                    try:
                        doc = etree.XML(arch_raw)
                    except Exception as e:
                        return
                    a_nodes = doc.xpath(".//a[@type='object' or @type='action']")
                    for node in a_nodes:
                        name = node.get('name')
                        if not name:
                            continue
                        string_val = ''.join(node.itertext()).strip()
                        if string_val:
                            domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name)]
                            if not store_model_nodes_obj.search(domain, limit=1):
                                store_model_nodes_obj.create({
                                    'model_id': self.model_id.id,
                                    'sh_node_option': 'kanban_link',
                                    'sh_attribute_name': name,
                                    'sh_attribute_string': string_val
                                })
                    button_nodes = doc.xpath(".//button[@type='object' or @type='action']")
                    for node in button_nodes:
                        name = node.get('name')
                        if not name:
                            continue
                        string_val = node.get('string') or ''.join(node.itertext()).strip()
                        if string_val:
                            domain = [('model_id', '=', self.model_id.id),('sh_attribute_name', '=', name)]
                            if not store_model_nodes_obj.search(domain, limit=1):
                                store_model_nodes_obj.create({
                                    'model_id': self.model_id.id,
                                    'sh_node_option': 'button',
                                    'sh_attribute_name': name,
                                    'sh_attribute_string': string_val
                                })

                if doc.xpath("//form"):
                    smt_button_division = doc.xpath("//div[@class='oe_button_box']")
                    if smt_button_division:
                        smt_button_division = etree.tostring(smt_button_division[0])
                        smt_button_division = etree.XML(smt_button_division)
                        smt_object_button = smt_button_division.xpath("//button[@type='object']")
                        self._get_smart_btn_string(smt_object_button,type='object')
                        smt_action_button = smt_button_division.xpath("//button[@type='action']")
                        self._get_smart_btn_string(smt_action_button,type='action')

                    page_list = doc.xpath("//page")
                    if page_list:
                        for page in page_list:
                            if page.get('string'):
                                domain = [('sh_attribute_string','=',page.get('string')),('model_id','=',self.model_id.id),('sh_node_option','=','page')]
                                if page.get('name'):
                                    domain += [('sh_attribute_name', '=', page.get('name'))]
                                if not store_model_nodes_obj.search(domain, limit=1):
                                    store_model_nodes_obj.create({
                                        'model_id': self.model_id.id,
                                        'sh_attribute_name': page.get('name'),
                                        'sh_attribute_string': page.get('string'),
                                        'sh_node_option': 'page',
                                    })

                    if self.model_name == 'res.config.settings':
                        for setting_page in doc.xpath("//div[@class='app_settings_block']"):
                            if setting_page.get('string'):
                                domain = [('sh_attribute_string','=',setting_page.get('string')),('model_id','=',self.model_id.id),('sh_node_option','=','page')]
                                if setting_page.get('data-key'):
                                    domain += [('sh_attribute_name', '=', setting_page.get('data-key'))]
                                if not store_model_nodes_obj.search(domain, limit=1):
                                    store_model_nodes_obj.create({
                                        'model_id': self.model_id.id,
                                        'sh_attribute_name': setting_page.get('data-key') or '',
                                        'sh_attribute_string': setting_page.get('string'),
                                        'sh_node_option': 'page',
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

class ShStoreModelData(models.Model):
    _name = 'sh.store.model.data'
    _description = 'Store Model Nodes'
    _rec_name = 'sh_attribute_string'

    
    model_id = fields.Many2one('ir.model', string='Model', index=True, ondelete='cascade',required=True, tracking=True)
    sh_node_option = fields.Selection([('button','Button'),('page','Page'),('link','Link'),('filter', 'Filter'), ('groupby', 'Group By'),('kanban_link', 'Kanban Link')],string="Node Option",required=True, tracking=True)
    sh_attribute_name = fields.Char('Attribute Name', tracking=True)
    sh_attribute_string= fields.Char('Attribute String',required=True, tracking=True)

    sh_button_type = fields.Selection([('object','Object'),('action','Action')],string="Button Type", tracking=True)
    sh_is_smart_button = fields.Boolean('Smart Button', tracking=True)