{
    'name': 'CR Auto Discount Fields',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Automatically fill discount code and note fields for Costa Rica electronic invoicing',
    'description': """
        This module automatically fills the discount_code_id and discount_note fields
        in invoice lines when a discount is applied, supporting Costa Rica electronic invoicing requirements.
    """,
    'author': 'SNG',
    'website': 'https://sngcloud.com',
    'depends': [
        'sale',
        'account',
        'cr_electronic_invoice',
    ],
    'data': [
        'data/discount_code_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
