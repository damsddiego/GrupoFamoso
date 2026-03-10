# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from ast import literal_eval
from odoo.exceptions import UserError, ValidationError


class SalesCommission(models.Model):
    _name = 'sales.commission'
    _description = 'Sales Commission'

    name = fields.Char(string='Commission Name', required=True)
    commission_type = fields.Selection([('standard', 'Standard'),('partner_based','Partner Based'), ('product_category_margin','Product/ Product Category/ Margin Based')], string="Commission Type", default='standard',  required=True)
    commission_apply_on = fields.Selection([('sale', 'Sales Confirmation'),('invoice','Invoice Validate'), ('invoice_payment','Customer Payment')], string="Commission Apply on", default='sale',  required=True,
    help="Set Commission Aplly as per your requirement.\n"
    "Sales Confirmation:When Quotation is confirmed then commission is calculated\n"
    "Invoice Validate:When the Invoice is validated then the commission is calculated\n"
    "Customer Payment:When the Invoice is paid then the commission is calculated\n"
    )
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, readonly=True)
    
    salesperson_ids = fields.Many2many('res.partner', 'partner_commission_rel', 'commission_id', 'partner_id', string='Sales Person', copy=False, domain="[('is_salesperson', '=', True)]", required=True)
    #standard
    standard_commission = fields.Float(string='Standard Commission %', copy=False)
    
    # Campos para comisiones por días de vencimiento
    commission_by_days = fields.Boolean(string='Commission by Days', default=False)
    days_0_30_commission = fields.Float(string='0-30 Days Commission %', copy=False)
    days_31_60_commission = fields.Float(string='31-60 Days Commission %', copy=False)
    days_61_90_commission = fields.Float(string='61-90 Days Commission %', copy=False)
    days_90_plus_commission = fields.Float(string='90+ Days Commission %', copy=False)
    
    #partner_based
    affiliated_partner_commission = fields.Float(string='Affiliated Partner Commission %', copy=False)
    non_affiliated_partner_commission = fields.Float(string='Non Affiliated Partner Commission %', copy=False)
    sales_commission_line = fields.One2many('sales.commission.line', 'sales_commission_id', 'Commission Line')

    @api.onchange('commission_type')
    def _onchange_commission_type(self):
        if self.commission_type:
            if self.commission_type == 'standard':
                self.affiliated_partner_commission = 0
                self.non_affiliated_partner_commission = 0
            if self.affiliated_partner_commission or self.non_affiliated_partner_commission:
                self.standard_commission = 0

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SalesCommission,self).create(vals_list)
        for r in res:
            ####
            existing_rec = self.env["sales.commission"].search([('salesperson_ids','in',r.salesperson_ids.ids)])
            existing_rec = existing_rec - r
            for rec in existing_rec:
                #chk start date between ext_start and ext_end date
                if rec.start_date <= r.start_date and rec.end_date >= r.start_date:
                    raise ValidationError(_("Can not create record for same user."))
                #chk end date between ext_start and ext_end date
                if rec.start_date <= r.end_date and rec.end_date >= r.end_date:
                    raise ValidationError(_("Can not create record for same user."))
                #chk start date small of ext_start and end date bigger than ext_end date
                if rec.start_date >= r.start_date and rec.end_date <= r.end_date:
                    raise ValidationError(_("Can not create record for same user."))
            ####        
            if r.commission_type == 'standard' and not r.standard_commission and not r.commission_by_days:
                raise ValidationError(_("'Standard Commission %' must be bigger than 0."))
            # Validar comisiones por días si están activas
            if r.commission_by_days:
                if not r.days_0_30_commission and not r.days_31_60_commission and not r.days_61_90_commission and not r.days_90_plus_commission:
                    raise ValidationError(_("At least one commission percentage by days must be set when 'Commission by Days' is enabled."))
            if r.commission_type == 'partner_based': 
                if not r.affiliated_partner_commission:
                    raise ValidationError(_("'Affiliated Partner Commission %' must be bigger than 0."))
                if not r.non_affiliated_partner_commission:
                    raise ValidationError(_("'Non Affiliated Partner Commission %' must be bigger than 0."))
        return res

    def write(self, vals):
        res = super(SalesCommission, self).write(vals)
        existing_rec = self.env["sales.commission"].search([('salesperson_ids','in',self.salesperson_ids.ids)])
        existing_rec = existing_rec - self
        for rec in existing_rec:
            #chk start date between ext_start and ext_end date
            if rec.start_date <= self.start_date and rec.end_date >= self.start_date:
                raise ValidationError(_("Can not create record for same user."))
            #chk end date between ext_start and ext_end date
            if rec.start_date <= self.end_date and rec.end_date >= self.end_date:
                raise ValidationError(_("Can not create record for same user."))
            #chk start date small of ext_start and end date bigger than ext_end date
            if rec.start_date >= self.start_date and rec.end_date <= self.end_date:
                raise ValidationError(_("Can not create record for same user."))
        if self.commission_type == 'standard' and not self.standard_commission and not self.commission_by_days:
                raise ValidationError(_("'Standard Commission %' must be bigger than 0."))
        # Validar comisiones por días si están activas
        if self.commission_by_days:
            if not self.days_0_30_commission and not self.days_31_60_commission and not self.days_61_90_commission and not self.days_90_plus_commission:
                raise ValidationError(_("At least one commission percentage by days must be set when 'Commission by Days' is enabled."))
        if self.commission_type == 'partner_based': 
            if not self.affiliated_partner_commission:
                raise ValidationError(_("'Affiliated Partner Commission %' must be bigger than 0."))
            if not self.non_affiliated_partner_commission:
                raise ValidationError(_("'Non Affiliated Partner Commission %' must be bigger than 0."))
        return res

class SalesCommissionLine(models.Model):
    _name = 'sales.commission.line'
    _description = 'Sales Commission'

    name = fields.Selection([('product', 'Product'),('product_category','Product Category')], string="Based On", default='product',  required=True)
    com_with = fields.Selection([('fix_price', 'Fix Price'),('margin','Margin'), ('commission_exception','Commission Exception')], string="With", default='fix_price',  required=True)
    product_id = fields.Many2one('product.product', string='Product')
    category_id = fields.Many2one('product.category', string='Category')
    target_price = fields.Float(string='Target Price')
    above_price_commission = fields.Float(string='Above Price Commission %')
    target_margin = fields.Float(string='Target Margin %')
    above_margin_commission = fields.Float(string='Above Margin Commission %')
    below_margin_commission = fields.Float(string='Below Margin Commission %')
    commission = fields.Float(string='Commission %')
    sales_commission_id = fields.Many2one('sales.commission', string='Sales Commission')
    currency_id = fields.Many2one(related='sales_commission_id.currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SalesCommissionLine,self).create(vals_list)
        for r in res:
            msg = ''
            raise_warning = 0
            warning = _("Value must be bigger than 0 for based on '%(name)s' With '%(com_with)s'.",
            name=r.name,
            com_with=r.com_with
            )
            if r.com_with == 'fix_price':
                if not r.target_price:
                    msg += "\n 'Target Price'"
                    raise_warning = 1
                    #raise ValidationError(_("'Target Price' must be bigger than 0."))
                if not r.above_price_commission:
                    msg += "\n 'Above Price Commission %'"
                    raise_warning = 1
                    #raise ValidationError(_("'Above Price Commission %' must be bigger than 0."))
            if r.com_with == 'margin': 
                if not r.target_margin:
                    msg += "\n 'Target Margin %'"
                    raise_warning = 1
                    #raise ValidationError(_("'Target Margin %' must be bigger than 0."))
                if not r.above_margin_commission:
                    msg += "\n 'Above Margin Commission %'"
                    raise_warning = 1
                    #raise ValidationError(_("'Above Margin Commission %' must be bigger than 0."))
                if not r.below_margin_commission:
                    msg += "\n 'Below Margin Commission %'"
                    raise_warning = 1
                    #raise ValidationError(_("'Below Margin Commission %' must be bigger than 0."))
            if r.com_with == 'commission_exception':
                if not r.commission:
                    msg += "\n 'Commission %'"
                    raise_warning = 1
            if raise_warning == 1:
                warning += _('%s ') % (msg)
                raise UserError(warning)
        return res

    def write(self,vals):
        res = super(SalesCommissionLine,self).write(vals)
        #for r in self:
        msg = ''
        raise_warning = 0
        warning = _("Value must be bigger than 0 for based on '%(name)s' With '%(com_with)s'.",
        name=self.name,
        com_with=self.com_with
        )
        if self.com_with == 'fix_price':
            if not self.target_price:
                msg += "\n 'Target Price'"
                raise_warning = 1
                #raise ValidationError(_("'Target Price' must be bigger than 0."))
            if not self.above_price_commission:
                msg += "\n 'Above Price Commission %'"
                raise_warning = 1
                #raise ValidationError(_("'Above Price Commission %' must be bigger than 0."))
        if self.com_with == 'margin':
            if not self.target_margin:
                msg += "\n 'Target Margin %'"
                raise_warning = 1
                #raise ValidationError(_("'Target Margin %' must be bigger than 0."))
            if not self.above_margin_commission:
                msg += "\n 'Above Margin Commission %'"
                raise_warning = 1
                #raise ValidationError(_("'Above Margin Commission %' must be bigger than 0."))
            if not self.below_margin_commission:
                msg += "\n 'Below Margin Commission %'"
                raise_warning = 1
                #raise ValidationError(_("'Below Margin Commission %' must be bigger than 0."))
        if self.com_with == 'commission_exception':
            if not self.commission:
                msg += "\n 'Commission %'"
                raise_warning = 1
        if raise_warning == 1:
            warning += _('%s ') % (msg)
            raise UserError(warning)
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
