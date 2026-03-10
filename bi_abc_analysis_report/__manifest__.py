# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Inventory ABC Analysis Report -Stock Demand, Cost and Risk Analysis',
    'version': '18.0.0.0',
    'category': 'Warehouse',
    'summary': 'Warehouse Abc Analysis Report Warehouse Demand Report Warehouse stock risk report warehouse most demanded product report warehouse product costing report inventory risk analysis report inventory demand analysis inventory product demand report stock demand',
    'description' :"""

        Inventory ABC Analysis Report in odoo,
        Stock ABC Report in odoo,
        Print ABC Report in Excel in odoo,
        Print ABC Data Report in odoo,
        Print ABC Graph Report in odoo,
        Filters for ABC Report in odoo,
        Classification for ABC Report in odoo,
    
    """,
    'author': 'BROWSEINFO',
    "price": 49,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.com/demo-request?app=bi_abc_analysis_report&version=18&edition=Community',
    'depends': ['sale_stock',],
    'data': [
        'security/ir.model.access.csv',
        'wizard/bi_abc_analysis_report_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://www.browseinfo.com/demo-request?app=bi_abc_analysis_report&version=18&edition=Community',
    "images":['static/description/Banner.gif'],
    'license': 'OPL-1',
}
