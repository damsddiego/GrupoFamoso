{
    "name": "SNG Partner Receivable Account",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Assign default customer receivable accounts by company",
    "author": "SNG",
    "depends": ["account"],
    "data": [
        "views/res_company_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "OPL-1",
}
