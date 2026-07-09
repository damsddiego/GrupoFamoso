# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_sale_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación salida (cliente)',
        domain="[('usage', '=', 'internal')]",
        help='Ubicación opcional para forzar la salida desde la bodega del cliente en esta orden.',
        copy=False,
    )

    @api.onchange('partner_id')
    def _onchange_partner_sale_location(self):
        for order in self:
            order.partner_sale_location_id = False
            if hasattr(order, 'team_id') and order.partner_id.team_id:
                order.team_id = order.partner_id.team_id

    def _get_partner_sale_location_warehouse(self):
        self.ensure_one()
        return self.partner_sale_location_id.warehouse_id

    def _get_default_sale_warehouse(self):
        self.ensure_one()
        default_warehouse_id = self.env['ir.default'].with_company(
            self.company_id.id
        )._get_model_defaults('sale.order').get('warehouse_id')
        if default_warehouse_id is not None:
            return self.env['stock.warehouse'].browse(default_warehouse_id)
        return self.user_id.with_company(self.company_id.id)._get_default_warehouse_id()

    @api.depends('user_id', 'company_id', 'partner_sale_location_id', 'partner_sale_location_id.warehouse_id')
    def _compute_warehouse_id(self):
        super()._compute_warehouse_id()
        editable_orders = self.filtered(lambda order: order.state in ('draft', 'sent') or not order.id)
        for order in editable_orders:
            if order.partner_sale_location_id:
                order.warehouse_id = order._get_partner_sale_location_warehouse()

    @api.onchange('partner_sale_location_id')
    def _onchange_partner_sale_location_set_warehouse(self):
        for order in self:
            if order.state not in ('draft', 'sent') and order.id:
                continue
            if order.partner_sale_location_id:
                order.warehouse_id = order._get_partner_sale_location_warehouse()
            else:
                order.warehouse_id = order._get_default_sale_warehouse()

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id=group_id)
        if self.partner_sale_location_id:
            vals['partner_sale_location_id'] = self.partner_sale_location_id.id
        return vals


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_location_final(self):
        self.ensure_one()
        partner_location = self.order_id.partner_shipping_id.property_stock_customer
        if partner_location and partner_location.usage == 'customer':
            return partner_location
        return self.env.ref('stock.stock_location_customers')

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id=group_id)
        if self.order_id.partner_sale_location_id:
            vals['partner_sale_location_id'] = self.order_id.partner_sale_location_id.id
        return vals
