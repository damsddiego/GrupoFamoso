# -*- coding: utf-8 -*-
{
    "name": "Sale Stock CR",
    "version": "18.0.1.0.3",
    "author": "SNG Cloud",
    "website": "https://sngcloud.com",
    "category": "Sale",
    "summary": "",
    "depends": [
        "account",
        "sale_stock",
        "report_xlsx",
        "cr_electronic_invoice",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
        "views/stock_quant_views.xml",
        "report/stock_deliveryslip_report.xml",
        "wizards/reports.xml",
        "wizards/consign_cxc_wizard_views.xml",
        "wizards/current_stock_location_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "application": False,
    "installable": True,
}
