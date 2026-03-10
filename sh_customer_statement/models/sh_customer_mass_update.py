# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models

class MassActionWizard(models.TransientModel):
    _name="sh.customer.mass.update"
    _description="Customer Statement Mass Update"

    sh_customer_update = fields.Selection([('add', 'Add'), ('remove', 'Remove')], string='Customer Overdue Statement Action',default="add")
    sh_update_customers_ids=fields.Many2many('res.partner',string="Customers" ,required=True)
    sh_statement_ids=fields.Many2many('sh.customer.statement.config',string='Statement Mass Update')

    # update Customers
    def update_customers(self):
        if self.sh_customer_update=='add':
            for partner in self.sh_update_customers_ids:
                for record in self.sh_statement_ids:
                    if partner not in record.sh_partner_ids:
                        record.write({'sh_partner_ids': [(4,partner.id)] })
        else:
            for partner in self.sh_update_customers_ids:
                for record in self.sh_statement_ids:
                    if partner in record.sh_partner_ids:
                        record.sh_partner_ids= [(3,partner.id)]
