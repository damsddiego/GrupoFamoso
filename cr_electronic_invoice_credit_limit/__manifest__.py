{
    'name': 'CR Electronic Invoice Credit Limit',
    'version': '18.0.1.1.0',
    'category': 'Accounting',
    'summary': 'Limit credit notes amount based on original invoice',
    'description': """
        This module extends the Costa Rican Electronic Invoice module to limit
        the creation of credit notes so that their total amount doesn't exceed
        the original invoice amount.
    """,
    'author': 'SNG',
    'website': 'https://www.sngcloud.com',
    'depends': ['cr_electronic_invoice', 'stock'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}