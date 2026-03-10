# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import  fields, models


class MassActionpartnerWizard(models.TransientModel):
    _name="sh.customer.config.mass.update"
    _description="Partner Statement Mass Update"

    sh_customer_config_update = fields.Selection([('add', 'Add'), ('remove', 'Remove')], string='Customer Overdue Statement Action',default="add")
    sh_update_config_ids=fields.Many2many('sh.customer.statement.config',string="Config" ,required=True)
    sh_selected_partner_ids=fields.Many2many('res.partner',string='Selected partners')

    # Update Customers Statement Config
    def update_customers_config(self):
        if self.sh_customer_config_update=='add':
            for record in self.sh_update_config_ids:
                for partner in self.sh_selected_partner_ids:
                    if partner not in record.sh_partner_ids:
                        record.write({'sh_partner_ids': [(4,partner.id)] })
        else:
            for record in self.sh_update_config_ids:
                for partner in self.sh_selected_partner_ids:
                    if partner in record.sh_partner_ids:
                        record.sh_partner_ids = [(3,partner.id)]
