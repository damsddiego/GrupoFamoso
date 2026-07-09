import odoo
from odoo import SUPERUSER_ID


def migrate(cr, version):
    cr.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '_tmp_assigned_salesperson'")
    if not cr.fetchone()[0]:
        return

    cr.execute("SELECT id, assigned_salesperson_id FROM _tmp_assigned_salesperson WHERE assigned_salesperson_id IS NOT NULL")
    rows = cr.fetchall()
    if not rows:
        cr.execute("DROP TABLE IF EXISTS _tmp_assigned_salesperson")
        return

    cr.execute("SELECT id FROM res_company ORDER BY id")
    company_ids = [row[0] for row in cr.fetchall()]
    if not company_ids:
        cr.execute("DROP TABLE IF EXISTS _tmp_assigned_salesperson")
        return

    env = odoo.api.Environment(cr, SUPERUSER_ID, {})

    for partner_id, salesperson_id in rows:
        partner = env['res.partner'].browse(partner_id)
        for company_id in company_ids:
            company = env['res.company'].browse(company_id)
            partner.with_company(company).write({'assigned_salesperson_id': salesperson_id})

    cr.execute("DROP TABLE IF EXISTS _tmp_assigned_salesperson")
