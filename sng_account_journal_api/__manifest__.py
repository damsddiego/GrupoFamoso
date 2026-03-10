{
    'name': 'SNG Account Journal API',
    'version': '18.0.1.0.0',
    'summary': 'Adds boolean check to Account Journals for API filtering',
    'description': """
        This module adds a boolean field 'Incluir en App' (include_in_app) 
        to Account Journals to be used by an external API for filtering.
    """,
    'category': 'Accounting',
    'author': 'SNG CLOUD',
    'depends': ['account'],
    'data': [
        'views/account_journal_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
