{
    'name': 'Rejected Invoice Tracker - Hacienda CR',
    'version': '18.0.2.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Track rejected electronic invoices and credit notes, and their replacement history for Hacienda CR',
    'description': """
        Rejected Invoice Tracker - Hacienda CR
        ======================================

        This module tracks electronic invoices and credit notes rejected by
        Hacienda (Costa Rica) and maintains a complete replacement history.

        **Features:**
        - Identify all invoices and credit notes rejected by Hacienda
        - Create replacement documents directly from a rejected one
        - Link an existing accepted document as a replacement
        - Full replacement history (supports multiple replacement attempts)
        - Dedicated view for rejected documents with replacement status
        - Chatter notifications on both rejected and replacement documents
        - Filter by document type (invoice / credit note)

        **Replacement History:**
        - Each rejected document can have multiple replacement attempts
        - Only the most recent replacement is marked as 'current'
        - Previous attempts remain in the historical record for audit purposes

        **Security:**
        - Respects standard Odoo accounting access rights
        - Validates that replacement documents are accepted by Hacienda
    """,
    'author': 'SNG Cloud',
    'website': 'https://www.sngcloud.com',
    'depends': [
        'account',
        'cr_electronic_invoice',
    ],
    'data': [
        'security/ir.rule.xml',
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'wizard/link_replacement_wizard_view.xml',
        'views/rejected_invoice_menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
