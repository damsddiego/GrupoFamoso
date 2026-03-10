{
    'name': 'Invoice Report by Salesperson',
    'version': '18.0.2.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Multi-company invoice reports by salesperson with on-screen view, Excel and PDF export',
    'description': """
        Invoice Report by Salesperson - Multi-Company Edition
        ======================================================

        This module allows generating comprehensive invoice reports filtered by:

        **Filters:**
        - Date range (from/to)
        - Multiple companies (respects user's allowed companies)
        - Salesperson (single or multiple)
        - Invoice type (invoices, credit notes, or all)
        - Payment status (all, paid, unpaid, partial, reversed, etc.)

        **Features:**
        - Multi-company support with native Odoo security rules
        - No sudo() usage - respects all access rights and record rules
        - View results on-screen using standard Odoo views (tree, pivot, graph)
        - Export to Excel (.xlsx) with professional formatting
        - Print PDF reports with company branding
        - Correct handling of credit notes and reversals (no double counting)
        - Grouped by salesperson with subtotals and grand totals

        **Reports can be:**
        - Viewed on screen (using native account.move views)
        - Exported to Excel format (.xlsx)
        - Printed as PDF

        **Security:**
        - Fully respects multi-company record rules
        - Users can only see invoices from companies they have access to
        - No bypass of security rules via sudo()
    """,
    'author': 'SNG Cloud',
    'website': 'https://www.sngcloud.com',
    'depends': [
        'account',
        'sales_commission_omax',
        'sng_invoice_assigned_salesperson',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/invoice_report_wizard_view.xml',
        'report/invoice_report.xml',
        'report/invoice_report_template.xml',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
