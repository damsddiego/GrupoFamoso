def migrate(cr, version):
    # Save existing integer values before Odoo converts the column to jsonb
    cr.execute("""
        CREATE TABLE IF NOT EXISTS _tmp_assigned_salesperson AS
        SELECT id, assigned_salesperson_id
        FROM res_partner
        WHERE assigned_salesperson_id IS NOT NULL
    """)
    # Drop views that depend on the column before dropping it
    cr.execute("DROP VIEW IF EXISTS payment_report_salesperson CASCADE")
    # Drop the column so Odoo can recreate it as jsonb (company_dependent)
    cr.execute("ALTER TABLE res_partner DROP COLUMN IF EXISTS assigned_salesperson_id")
