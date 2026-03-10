# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    commission_analysis_line = fields.One2many('sales.commission.analysis','move_id','Sales Commission')
    created_by_commission = fields.Boolean('Created from Sales Commission')
    salesperson_id = fields.Many2one(
        'res.partner', 'Salesperson', 
        domain="[('is_salesperson', '=', True)]", 
        help="Salesperson assigned to this invoice for commission purposes.",
        compute='_compute_salesperson_id',
        store=True,
        readonly=False,
        precompute=True,
        default=lambda self: self.env.user.partner_id,
    )

    @api.depends('partner_id', 'partner_id.assigned_salesperson_id', 'invoice_user_id')
    def _compute_salesperson_id(self):
        for move in self:
            if move.partner_id and move.partner_id.assigned_salesperson_id:
                move.salesperson_id = move.partner_id.assigned_salesperson_id
            else:
                move.salesperson_id = (
                    move.salesperson_id
                    or move.invoice_user_id.partner_id
                    or self.env.user.partner_id
                )

    def _get_commission_salesperson(self):
        self.ensure_one()
        return self.salesperson_id or self.invoice_user_id.partner_id or self.env.user.partner_id

    def _get_commission_payment_date(self):
        self.ensure_one()
        receivable_lines = self.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        partials = receivable_lines.mapped('matched_debit_ids') | receivable_lines.mapped('matched_credit_ids')
        counterpart_lines = (
            partials.mapped('debit_move_id') | partials.mapped('credit_move_id')
        ).filtered(lambda line: line.move_id != self)

        dates = [date for date in counterpart_lines.mapped('payment_id.date') if date]
        dates += [date for date in partials.mapped('max_date') if date]
        dates += [date for date in counterpart_lines.mapped('date') if date]
        return max(dates) if dates else False

    def _get_commission_analysis_date(self, commission):
        self.ensure_one()
        if commission.commission_apply_on == 'invoice_payment':
            return self._get_commission_payment_date() or self.invoice_date or fields.Date.context_today(self)
        if commission.commission_apply_on == 'invoice':
            return self.invoice_date or fields.Date.context_today(self)
        return fields.Date.context_today(self)

    def create_product_commission_analysis_line(self, commission, commission_line, order_lines):
        salesperson = self._get_commission_salesperson()
        if not salesperson:
            return
        analysis_date = self._get_commission_analysis_date(commission)
        for line in order_lines:
            #Fix Price
            if commission_line.com_with == 'fix_price':
                ####cur
                if commission.currency_id != self.currency_id:
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                ####
                price_subtotal_per_qty = price_subtotal/line.quantity
                if price_subtotal_per_qty >= commission_line.target_price:
                    commission_percentage = commission_line.above_price_commission
                    #name = "Product/ Product Category/ Margin Based(Fix Price) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                    name = "Product/ (Fix Price) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                    commission_amount = (price_subtotal * commission_percentage) / 100
                    if commission_amount > 0:#
                        vals = {
                            'name':name,
                            'date':analysis_date,
                            'sales_person_id':salesperson.id,
                            'move_id':self.id,
                            'commission_id':commission.id,
                            'commission_type':commission.commission_type,
                            'product_id':line.product_id.id,
                            'commission_amount':commission_amount
                        }
                        self.env["sales.commission.analysis"].sudo().create(vals)
            #Margin
            if commission_line.com_with == 'margin':
                #ref sale_margin
                purchase_price = self.get_purchase_price(line)
                #############Cur
                if commission.currency_id != self.currency_id:
                    purchase_price = self.currency_id._convert(purchase_price, commission.currency_id, commission.company_id, self.invoice_date)
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                #############3
                margin = price_subtotal - (purchase_price * line.quantity)
                #line.margin = line.price_subtotal - (line.purchase_price * line.quantity)
                margin_percent = (margin/price_subtotal)*100
                ##
                
                if margin_percent >= commission_line.target_margin:
                    commission_percentage = commission_line.above_margin_commission
                    commission_amount = (margin * commission_percentage) / 100
                if margin_percent <= commission_line.target_margin:
                    commission_percentage = commission_line.below_margin_commission
                    commission_amount = (margin * commission_percentage) / 100
                #name = "Product/ Product Category/ Margin Based(Margin) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                name = "Product/ (Margin Based) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                if commission_amount > 0:#
                    vals = {
                        'name':name,
                        'date':analysis_date,
                        'sales_person_id':salesperson.id,
                        'move_id':self.id,
                        'commission_id':commission.id,
                        'commission_type':commission.commission_type,
                        'product_id':line.product_id.id,
                        'commission_amount':commission_amount
                    }
                    self.env["sales.commission.analysis"].sudo().create(vals)
            #Commission Exception
            if commission_line.com_with == 'commission_exception':
                commission_percentage = commission_line.commission
                name = "Product/ (Commission Exception) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                ####cur
                if commission.currency_id != self.currency_id:
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                ####
                commission_amount = (price_subtotal * commission_percentage) / 100
                if commission_amount > 0:#
                    vals = {
                        'name':name,
                        'date':analysis_date,
                        'sales_person_id':salesperson.id,
                        'move_id':self.id,
                        'commission_id':commission.id,
                        'commission_type':commission.commission_type,
                        'product_id':line.product_id.id,
                        'commission_amount':commission_amount
                    }
                    self.env["sales.commission.analysis"].sudo().create(vals)

    def create_product_categ_commission_analysis_line(self, commission, commission_line, order_lines):
        salesperson = self._get_commission_salesperson()
        if not salesperson:
            return
        analysis_date = self._get_commission_analysis_date(commission)
        for line in order_lines:
            #Fix Price
            if commission_line.com_with == 'fix_price':
                ####cur
                if commission.currency_id != self.currency_id:
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                ####
                price_subtotal_per_qty = price_subtotal/line.quantity
                if price_subtotal_per_qty >= commission_line.target_price:
                    commission_percentage = commission_line.above_price_commission
                    #name = "Product/ Product Category/ Margin Based(Fix Price) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                    name = "Product Category/ (Fix Price) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                    commission_amount = (price_subtotal * commission_percentage) / 100
                    if commission_amount > 0:#
                        vals = {
                            'name':name,
                            'date':analysis_date,
                            'sales_person_id':salesperson.id,
                            'move_id':self.id,
                            'commission_id':commission.id,
                            'commission_type':commission.commission_type,
                            'product_id':line.product_id.id,
                            'category_id':line.product_id.categ_id.id,#add
                            'commission_amount':commission_amount
                        }
                        self.env["sales.commission.analysis"].sudo().create(vals)
            #Margin
            if commission_line.com_with == 'margin':
                #ref sale_margin
                purchase_price = self.get_purchase_price(line)
                #############Cur
                if commission.currency_id != self.currency_id:
                    purchase_price = self.currency_id._convert(purchase_price, commission.currency_id, commission.company_id, self.invoice_date)
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                #############3
                
                margin = price_subtotal - (purchase_price * line.quantity)
                #line.margin = line.price_subtotal - (line.purchase_price * line.quantity)
                margin_percent = (margin/price_subtotal)*100
                ##
                
                if margin_percent >= commission_line.target_margin:
                    commission_percentage = commission_line.above_margin_commission
                    commission_amount = (margin * commission_percentage) / 100
                if margin_percent <= commission_line.target_margin:
                    commission_percentage = commission_line.below_margin_commission
                    commission_amount = (margin * commission_percentage) / 100
                #name = "Product/ Product Category/ Margin Based(Margin) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                name = "Product Category/ (Margin Based) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                if commission_amount > 0:#
                    vals = {
                        'name':name,
                        'date':analysis_date,
                        'sales_person_id':salesperson.id,
                        'move_id':self.id,
                        'commission_id':commission.id,
                        'commission_type':commission.commission_type,
                        'product_id':line.product_id.id,
                        'category_id':line.product_id.categ_id.id,#add
                        'commission_amount':commission_amount
                    }
                    self.env["sales.commission.analysis"].sudo().create(vals)
            #Commission Exception
            if commission_line.com_with == 'commission_exception':
                commission_percentage = commission_line.commission
                name = "Product Category/ (Commission Exception) (" + str(commission_percentage) + " %) for Product " + str(line.product_id.name)
                ####cur
                if commission.currency_id != self.currency_id:
                    price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
                else:
                    price_subtotal = line.price_subtotal
                ####
                commission_amount = (price_subtotal * commission_percentage) / 100
                if commission_amount > 0:#
                    vals = {
                        'name':name,
                        'date':analysis_date,
                        'sales_person_id':salesperson.id,
                        'move_id':self.id,
                        'commission_id':commission.id,
                        'commission_type':commission.commission_type,
                        'product_id':line.product_id.id,
                        'category_id':line.product_id.categ_id.id,#add
                        'commission_amount':commission_amount,
                    }
                    self.env["sales.commission.analysis"].sudo().create(vals)

    def get_days_difference(self):
        """Calculate the difference in days between invoice date and due date"""
        if self.invoice_date and self.invoice_date_due:
            return (self.invoice_date_due - self.invoice_date).days
        return 0

    def get_commission_percentage_by_days(self, commission, days):
        """Get commission percentage based on days difference"""
        if days <= 30:
            return commission.days_0_30_commission
        elif days <= 60:
            return commission.days_31_60_commission
        elif days <= 90:
            return commission.days_61_90_commission
        else:
            return commission.days_90_plus_commission

    def create_standard_commission(self, commission):
        salesperson = self._get_commission_salesperson()
        if not salesperson:
            return
        analysis_date = self._get_commission_analysis_date(commission)
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            # Si la comisión está basada en días, calcular el porcentaje según los días
            if commission.commission_by_days:
                days = self.get_days_difference()
                commission_percentage = self.get_commission_percentage_by_days(commission, days)
                name = "Standard Commission by Days (" + str(commission_percentage) + " %) for " + str(line.product_id.name) + " (" + str(days) + " days)"
            else:
                commission_percentage = commission.standard_commission
                name = "Standard Commission (" + str(commission_percentage) + " %) for " + str(line.product_id.name)
            
            ####cur
            if commission.currency_id != self.currency_id:
                price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
            else:
                price_subtotal = line.price_subtotal
            ####
            commission_amount = (price_subtotal * commission_percentage) / 100
            if commission_amount > 0:#
                vals = {
                    'name':name,
                    'date':analysis_date,
                    'sales_person_id':salesperson.id,
                    'move_id':self.id,
                    'commission_id':commission.id,
                    'commission_type':commission.commission_type,
                    'commission_amount':commission_amount
                }
                self.env["sales.commission.analysis"].sudo().create(vals)

    def create_partner_based_commission(self, commission):
        salesperson = self._get_commission_salesperson()
        if not salesperson:
            return
        analysis_date = self._get_commission_analysis_date(commission)
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            if self.partner_id.affiliated:
                commission_percentage = commission.affiliated_partner_commission
                partner_type = 'Affiliated'
            else:
                commission_percentage = commission.non_affiliated_partner_commission
                partner_type = 'Non Affiliated'
            
            name = "Partner Based Commission (" + str(commission_percentage) + " %) for '" + str(partner_type)+ "' " + str(self.partner_id.name)
            ####cur
            if commission.currency_id != self.currency_id:
                price_subtotal = self.currency_id._convert(line.price_subtotal, commission.currency_id, commission.company_id, self.invoice_date)
            else:
                price_subtotal = line.price_subtotal
            ####
            commission_amount = (price_subtotal * commission_percentage) / 100
            if commission_amount > 0:#
                vals = {
                    'name':name,
                    'date':analysis_date,
                    'sales_person_id':salesperson.id,
                    'move_id':self.id,
                    'commission_id':commission.id,
                    'commission_type':commission.commission_type,
                    'partner_id':self.partner_id.id,
                    'partner_type':partner_type,
                    'commission_amount':commission_amount
                }
                self.env["sales.commission.analysis"].sudo().create(vals)

    def _post(self, soft=True):#def
        res = super(AccountMove, self)._post(soft)
        #commission_on_invoice=self.env['ir.config_parameter'].sudo().get_param('commission_on_invoice')
        #if commission_on_invoice == 'True':
        for rec in self:
            salesperson = rec.salesperson_id or rec.invoice_user_id.partner_id
            if not salesperson:
                continue
            #commission = self.env["sales.commission"].sudo().search([('company_id','=',self.env.company.id), ('salesperson_ids','in',rec.salesperson_id.id)])
            commission = self.env["sales.commission"].sudo().search([('company_id','=',self.env.company.id), ('salesperson_ids','in',salesperson.id),('start_date','<=',rec.invoice_date),('end_date','>=',rec.invoice_date), ('commission_apply_on','=','invoice')])
            
            if commission and rec.move_type == 'out_invoice':
                #Standard
                if commission.commission_type == 'standard':
                    rec.create_standard_commission(commission)
                #Partner Based
                if commission.commission_type == 'partner_based':
                    rec.create_partner_based_commission(commission)
                #Product/ Product Category/ Margin Based
                if commission.commission_type == 'product_category_margin':
                    for commission_line in commission.sales_commission_line:
                        ###PRODUCT###
                        if commission_line.name == 'product':
                            order_lines = rec.invoice_line_ids.filtered(lambda l: l.product_id.id == commission_line.product_id.id)
                            rec.create_product_commission_analysis_line(commission, commission_line, order_lines)
                        ###PRODUCT Category###
                        if commission_line.name == 'product_category':
                            order_lines =  rec.invoice_line_ids.filtered(lambda l: l.product_id.categ_id.id == commission_line.category_id.id)
                            rec.create_product_categ_commission_analysis_line(commission, commission_line, order_lines)
        return res

    def button_draft(self):#def
        res = super(AccountMove, self).button_draft()
        for rec in self:
            remove_line = []
            if rec.commission_analysis_line:
                for line in rec.commission_analysis_line:
                    remove_line.append((2, line.id))
                rec.commission_analysis_line = remove_line#remove existing lines
        return res

    def get_purchase_price(self,line):
        line = line.with_company(line.company_id)
        # Convert the cost to the line UoM
        product_cost = line.product_id.uom_id._compute_price(
            line.product_id.standard_price,
            line.product_uom_id,
        )
        purchase_price = self._convert_to_sol_currency(
            product_cost,
            line.product_id.cost_currency_id)
        return purchase_price

    def _convert_to_sol_currency(self, amount, currency):#ref SOLine
        """Convert the given amount from the given currency to the SO(L) currency.

        :param float amount: the amount to convert
        :param currency: currency in which the given amount is expressed
        :type currency: `res.currency` record
        :returns: converted amount
        :rtype: float
        """
        self.ensure_one()
        to_currency = self.currency_id
        if currency and to_currency and currency != to_currency:
            conversion_date = self.invoice_date or fields.Date.context_today(self)
            company = self.company_id or self.env.company
            return currency._convert(
                from_amount=amount,
                to_currency=to_currency,
                company=company,
                date=conversion_date,
                round=False,
            )
        return amount

    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_reconciled_info(self):
        super(AccountMove, self)._compute_payments_widget_reconciled_info()
        #commission_on_payment=self.env['ir.config_parameter'].sudo().get_param('commission_on_payment')
        #if commission_on_payment == 'True':
        for move in self:
            if move.move_type == 'out_invoice':
                salesperson = move.salesperson_id or move.invoice_user_id.partner_id
                if not salesperson:
                    continue
                commission = self.env["sales.commission"].sudo().search([('company_id','=',self.env.company.id), ('salesperson_ids','in',salesperson.id),('start_date','<=',move.invoice_date),('end_date','>=',move.invoice_date), ('commission_apply_on','=','invoice_payment')])
                if not move.amount_residual and not move.commission_analysis_line and commission:
                    #Standard
                    if commission.commission_type == 'standard':
                        move.create_standard_commission(commission)
                    #Partner Based
                    if commission.commission_type == 'partner_based':
                        move.create_partner_based_commission(commission)
                    #Product/ Product Category/ Margin Based
                    if commission.commission_type == 'product_category_margin':
                        for commission_line in commission.sales_commission_line:
                            ###PRODUCT###
                            if commission_line.name == 'product':
                                order_lines = move.invoice_line_ids.filtered(lambda l: l.product_id.id == commission_line.product_id.id)
                                move.create_product_commission_analysis_line(commission, commission_line, order_lines)
                            ###PRODUCT Category###
                            if commission_line.name == 'product_category':
                                order_lines =  move.invoice_line_ids.filtered(lambda l: l.product_id.categ_id.id == commission_line.category_id.id)
                                move.create_product_categ_commission_analysis_line(commission, commission_line, order_lines)

                if commission:
                    if move.amount_residual and move.commission_analysis_line:
                        move.commission_analysis_line = False
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
