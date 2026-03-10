# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models, fields
from odoo.exceptions import UserError, ValidationError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def unlink(self):
        commission_product = self.env.ref('sales_commission_omax.sales_commission_product_0')
        if self.id == commission_product.id:
            raise ValidationError(_("The '%s' is a commission product restricted for delete. It is important for Sales commission flow.", self.name))
        return super(ProductProduct, self).unlink()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def unlink(self):
        commission_product = self.env.ref('sales_commission_omax.sales_commission_product_0')
        if commission_product.id in self.product_variant_ids.ids:
            raise ValidationError(_("The '%s' is a commission product restricted for delete. It is important for Sales commission flow.", self.name))
        return super(ProductProduct, self).unlink()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
