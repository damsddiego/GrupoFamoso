{
    'name': 'Associate Assigned Salesperson to Invoice and Sales Order',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Add assigned salesperson field to invoices and sales orders',
    'description': """
        This module adds the 'assigned_salesperson_id' field to the account.move
        and sale.order models, related to the partner's assigned salesperson.
    """,
    'author': 'SNG Cloud',
    'depends': ['account', 'sale', 'sales_commission_omax'],
    'data': [
        'views/account_move_view.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
