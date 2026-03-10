# -*- coding: utf-8 -*-
{
    'name' : 'Account Tax Report',
    'version':'18.0.1.0',
    'category': 'Accounting,Sales,Purchases',
    'sequence': 1,
    'author': 'OMAX Informatics',
    'website': 'https://www.omaxinformatics.com',
    'description' : '''
            This module helps to generate Sales and Purchase tax teport in PDF and Excel format.
			''',
    'depends' : ['account','sale','purchase'],
    'data':[
        'security/ir.model.access.csv',
        'wizard/tax_report_wizard.xml',
        'wizard/tax_report_wizard_sales.xml',
        'wizard/tax_report_wizard_purchases.xml',
        'security/ir_model_access.xml',
        'report/report.xml',
        'report/report_menu.xml',
    ],
    'images':['static/description/banner.png'],
    'license':'OPL-1', 
    'currency':'USD',
    'price': 35.00,
    'demo':[],
    'test':[],
    'application':True,
    'installable':True,
    'auto_install':False,
    'pre_init_hook': 'pre_init_check',
    'module_type': 'official',
    'summary': '''
   The Tax Report for Sales & Purchases provides a detailed summary of all taxable transactions during a specific reporting period (monthly, quarterly, or annually). 
    It helps in determining the total tax collected on sales and the total tax paid on purchases to compute the net tax liability or input credit.

    The Tax Report for Sales and Purchases is a key component of financial and tax compliance for businesses. It provides a detailed breakdown of taxable 
    transactions and is especially important for VAT (Value Added Tax), GST (Goods and Services Tax), and similar indirect tax systems.

    Account Tax Report based on Sales and Purchases.
    Advanced level filtering by Partners, Product Categoty, Products, SalesTeam, SalesPerson and Taxes.
    Supported multi-company & multi-currency.
    User able to Generate Tax Report with Detailed Information.
    Supported in PDF & Excel format.

    Generate detailed Account Tax Reports for Sales and Purchases with advanced filters by Partner, Product, Category, Sales Team, Salesperson, and Taxes. Export reports instantly in PDF and Excel formats.
    sales tax report purchase tax report GST report VAT report tax summary report tax analysis report 
    partner tax report product tax report product category tax report sales team tax report salesperson tax report tax by product tax by partner tax by sales team 
    excel tax report pdf tax report export tax report tax report accounting report  odoo financial report odoo gst vat report
    ''',
}
