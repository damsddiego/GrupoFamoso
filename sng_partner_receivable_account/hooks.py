DEFAULT_RECEIVABLE_ACCOUNTS = {
    1: 137,
    2: 794,
    3: 863,
}

DEFAULT_PAYABLE_ACCOUNTS = {
    1: 180,
    2: 799,
    3: 1742,
}


def post_init_hook(env):
    companies = env["res.company"].sudo().browse(DEFAULT_RECEIVABLE_ACCOUNTS)
    accounts = env["account.account"].sudo()
    for company in companies.exists():
        account = accounts.browse(DEFAULT_RECEIVABLE_ACCOUNTS[company.id])
        if account.exists() and account.account_type == "asset_receivable":
            company.sng_default_receivable_account_id = account.id

    companies = env["res.company"].sudo().browse(DEFAULT_PAYABLE_ACCOUNTS)
    for company in companies.exists():
        account = accounts.browse(DEFAULT_PAYABLE_ACCOUNTS[company.id])
        if account.exists() and account.account_type == "liability_payable":
            company.sng_default_payable_account_id = account.id

    env["res.partner"].sudo()._sng_assign_default_receivable_accounts()
    env["res.partner"].sudo()._sng_assign_default_payable_accounts()
