{
    'name': 'SNG Control Sale',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Block sale confirmations without sufficient stock per warehouse',
    'description': """
        Blocks sale order confirmation when there is not enough available stock
        in the selected warehouse. Only storable products are validated.
    """,
    'author': 'SNG',
    'website': 'https://www.sngcloud.com',
    'depends': [
        'sale',
        'stock',
        'sale_account_manager_customer_credit_limit_approval',
    ],
    'data': [
        'security/security.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
