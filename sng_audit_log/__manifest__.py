{
    'name': 'SNG Audit Log',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Audit create, update, and delete operations on key models',
    'description': """
        Keeps an audit trail for sensitive business records, especially
        deletions that would otherwise leave no trace in Odoo.
    """,
    'author': 'SNG',
    'depends': [
        'account',
        'product',
        'sale',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sng_audit_log_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
