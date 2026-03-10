# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name':'Sales Commission',
    'author': 'OMAX Informatics',
    'version': '1.1',
    'support':'omaxinformatics@gmail.com',
    'website': 'https://www.omaxinformatics.com',
    'category':'Sales,Accounting',
    'description': '''
        Sales Commission based on different criteria and different trigger points.
        This enhanced version allows commission calculations based on the number of days an invoice has been outstanding.
    ''',
    'depends': ['sale', 'account', 'product', 'uom'],#uom bcz data file
	'data': [
	    'security/group_security.xml',
	    'security/ir.model.access.csv',
	    'data/product_data.xml',
	    'data/commission_days_data.xml',
	    'data/cleanup_action.xml',
	    'wizard/create_commission_bill_wiz.xml',
	    'wizard/sales_commission_report_wiz.xml',
	    'views/sales_commission.xml',
	    'views/sales_commission_analysis.xml',
	    'views/res_partner_view.xml',
	    'views/sale_order.xml',
	    'views/account_move.xml',
	    'views/account_payment.xml',
	    'report/report.xml',
        'report/report_menu.xml',
	],
    'demo': [
        'demo/commission_demo.xml',
    ],
    'test':[],
    'images': ['static/description/banner.png'],
    'license': 'OPL-1',
    'currency':'USD',
    'price': 50,
    'installable' : True,
    'auto_install' : False,
    'application' : True,
    'pre_init_hook': 'pre_init_check',
    'module_type': 'official',
    'summary': '''
    This application allows user to create and manage commissions for salespersons for a specific period. You can set a sales commission for a specific date internally which helps to generate sales commission for monthly, quarterly or for specific date periods. We have provided option to calculate commission based on sales order confirmation, invoice is validate and invoice is paid. User can print pdf/excel report of commission analysis line with multiple filter options.commission, Calculate Commission in 3 ways for specific period. When quotation confirm then calculate commission, When invoice validate then calculate commission, When invoice paid then calculate commission, Standard Commission, Partner Based Commission, Product Based Commission, Product Category Based Commission, Margin Based Commission,Commission calculated based on sale order confirmation.Commission calculated based on invoice is validate.Commission calculated based on invoice is paid.User create commission for specific time period.Different commission type options available in commisson form.Different commission type options available in commisson form like Standard, Partner Based, Product/Product Category/ Margin Based Commissions.Calculate the commission based on any product or product category.Calculate the commission based on the margin percentage or margin amount.
Calculate the commission based on partner.User can see commission analysis and print commission report in pdf/excel format for specific sales person between selected dates and different Commission type filter options.User can generate invoice from commission line using group by of sales person.Easy to track generated invoices by commission line.
This enhanced version also allows commission calculations based on the number of days an invoice has been outstanding:
- 0-30 days: X% commission
- 31-60 days: Y% commission
- 61-90 days: Z% commission
- 90+ days: W% commission
    ''',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:        
