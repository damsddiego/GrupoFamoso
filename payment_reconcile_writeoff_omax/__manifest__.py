# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Reconcile Payment with Invoices, Bills. Support Write-off feature',
    'version': '18.0.1.0',
    'category': 'Accounting,Sales,Purchases',
    'sequence': 1,
    'author': 'OMAX Informatics',
    'website': 'https://www.omaxinformatics.com',
    'description' : '''
        This module help to reconcile invoices or bills directly from the payment form and user can reconciliation with write-off amount too.
    ''',
    'depends' : ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move.xml',
        'views/account_payment.xml',
    ],
    'images':['static/description/banner.png'],
    'license': 'OPL-1',
    'currency':'USD',
    'price': 45.00,
    'demo': [],
    'test': [],
    'installable' : True,
    'auto_install' : False,
    'application' : True,
    'pre_init_hook': 'pre_init_check',
    'module_type': 'official',
    'summary': '''
        This module help to reconcile invoices or bills directly from the payment form and user can reconciliation with write-off amount too.
        Reconcile payments with invoices and bills directly from the payment form in Odoo. Supports write-offs and accurate journal entries to streamline accounting and handle discrepancies with ease.
        reconcile outstanding Payments against with multiple Invoices reconcile outstanding Payments against with multiple bills Reconcile customer payments Reconcile vendor payments Multiple Reconcile invoices  Multiple Reconcile bills bill reconcile invoice reconcile payment reconcile
        Odoo payment reconciliation, reconcile payment invoices, reconcile payment bills, payment with write-off, invoice write-off, bill write-off, Odoo payment write-off, payment reconciliation module, reconcile directly from payment form, Odoo payment discrepancies, adjust payment invoices, reconcile invoices and bills, write-off account, write-off journal entry, Odoo accounting reconciliation, reconcile outstanding invoices, reconcile small balances payment adjustment with Invoices payment adjustment with bills write off payments write off customer payment write off vendor payments 
    '''
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
