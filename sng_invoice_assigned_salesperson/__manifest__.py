{
    'name': 'Associate Assigned Salesperson to Invoice',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Add assigned salesperson field to invoices',
    'description': """
        This module adds the 'assigned_salesperson_id' field to the account.move model,
        related to the partner's assigned salesperson.
    """,
    'author': 'SNG Cloud',
    'depends': ['account', 'sales_commission_omax'],
    'data': [
        'views/account_move_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
