# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Customer Account Statement",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "version": "18.0.10.0.0",
    "category": "Accounting",
    "summary": "Customer Payment Followup Print Customer Statement Report Customer Bank Statement Client Statement Contact Statement Overdue Statement Partner Statement of Account Print Overdue Statement send customer statement Account Statement Report print account statement customer overdue statement print customer overdue statement customer statement generator send overdue statement client Payment Followup Print client Statement Report client Bank Statement Client Statement Contact Statement Overdue Statement Partner Statement of Account Print Overdue Statement send client statement Account Statement Report print account statement client overdue statement print client overdue statement client statement generator send overdue statement user Payment Followup Print user Statement Report user Bank Statement user Statement Contact Statement Overdue Statement Partner Statement of Account Print Overdue Statement send user statement Account Statement Report print account statement user overdue statement print user overdue statement user statement generator send overdue statement partner Payment Followup Print partner Statement Report partner Bank Statement partner Statement Contact Statement Overdue Statement Partner Statement of Account Print Overdue Statement send partner statement Account Statement Report print account statement partner overdue statement print partner overdue statement partner statement generator send overdue statement Send Customer Statements Customer Account Statement Reports Customer Account Statements Print Overdue Statement Report Send Overdue Statement Report Print Supplier Statements accounts statement partner ledger customer ledger statement of accounts Mass Action PDF Print Mass Action XLS Export Bulk Email Sending Date Range Filter Mass Action Bucket Wise Mass Action Without Bucket Processing Bulk PDF XLS Print Odoo Mass Action Feature Bulk Record Processing Mass Action Email Export Odoo",

    "description": """This module allows customers to see statements as well as overdue statement details. You can send statements by email to the customers. You can also see customers mail log history with statements and overdue statements. You can also send statements automatically weekly, monthly & daily using cron job. You can filter statements by dates, statements & overdue statements. You can group by statements by the statement type, mail sent status & customers. You can print statements and overdue statements.""",
    "depends": [
        'account',
    ],
    'assets': {
        'web.assets_frontend': [
            'sh_customer_statement/static/src/js/portal.js',
        ]
    },
    "data": [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'report/sh_customer_statement_report_templates.xml',
        'report/sh_customer_due_statement_report_templates.xml',
        'report/sh_customer_filter_statement_report_templates.xml',
        'data/mail_template_data.xml',
        'views/res_user_views.xml',
        'wizard/mail_compose_view.xml',
        'wizard/customer_statement_mass_action.xml',
        'wizard/sh_send_customer_statement_wizard.xml',
        'wizard/customer_config_update_wizard.xml',
        'views/mail_history.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/customer_statement_menus.xml',
        'views/sh_customer_statement_portal_templates.xml',
    ],
    "images": ["static/description/background.png", ],
    "license": "OPL-1",
    "installable": True,
    "auto_install": False,
    "application": True,
    "price":"42",
    "currency": "EUR"
}
