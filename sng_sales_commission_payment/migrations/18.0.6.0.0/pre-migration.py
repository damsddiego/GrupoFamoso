# -*- coding: utf-8 -*-
"""Cuadros de comisiones (sng.commission.scheme).

Hasta la 18.0.5.x cada tramo y cada mensual pertenecían a una compañía. Desde
la 18.0.6.0.0 pertenecen a un cuadro, que puede abarcar varias compañías. Aquí
lo existente se convierte en un cuadro por compañía, sin fecha de vigencia,
para que la actualización no cambie ninguna comisión: el cuadro de grupo se
crea después, a mano, y rige desde su «Vigente desde».

Va en SQL y antes de la carga del módulo porque el ORM todavía no conoce el
modelo y porque ``scheme_id`` es obligatorio. Si el -u se interrumpe se puede
volver a correr; una vez terminado ya no, porque Odoo elimina la columna
``company_id`` del tramo al final de la actualización.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        CREATE TABLE IF NOT EXISTS sng_commission_scheme (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            date_start DATE
        )""")
    cr.execute("""
        CREATE TABLE IF NOT EXISTS sng_commission_scheme_company_rel (
            scheme_id INTEGER NOT NULL REFERENCES sng_commission_scheme(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES res_company(id) ON DELETE CASCADE,
            PRIMARY KEY (scheme_id, company_id)
        )""")
    cr.execute("ALTER TABLE sng_commission_tier ADD COLUMN IF NOT EXISTS scheme_id INTEGER")
    cr.execute("ALTER TABLE sng_commission_monthly ADD COLUMN IF NOT EXISTS scheme_id INTEGER")

    # Un cuadro por compañía que tenga tramos o mensuales todavía sin cuadro.
    cr.execute("""
        SELECT c.id, c.name
          FROM res_company c
         WHERE EXISTS (SELECT 1 FROM sng_commission_tier t
                        WHERE t.company_id = c.id AND t.scheme_id IS NULL)
            OR EXISTS (SELECT 1 FROM sng_commission_monthly m
                        WHERE m.company_id = c.id AND m.scheme_id IS NULL)
         ORDER BY c.id""")
    for company_id, name in cr.fetchall():
        cr.execute(
            "INSERT INTO sng_commission_scheme (name, active) VALUES (%s, TRUE) RETURNING id", (name,))
        scheme_id = cr.fetchone()[0]
        cr.execute(
            "INSERT INTO sng_commission_scheme_company_rel (scheme_id, company_id) VALUES (%s, %s)",
            (scheme_id, company_id))
        cr.execute(
            "UPDATE sng_commission_tier SET scheme_id = %s WHERE company_id = %s AND scheme_id IS NULL",
            (scheme_id, company_id))
        cr.execute(
            "UPDATE sng_commission_monthly SET scheme_id = %s WHERE company_id = %s AND scheme_id IS NULL",
            (scheme_id, company_id))

    # El cuadro por defecto del archivo de datos (noupdate) es el de la compañía
    # del tramo de fábrica: sin este xmlid la actualización crearía otro.
    cr.execute("""
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT d.module, 'sng_commission_scheme_default', 'sng.commission.scheme', t.scheme_id, TRUE
          FROM ir_model_data d
          JOIN sng_commission_tier t ON t.id = d.res_id
         WHERE d.module = 'sng_sales_commission_payment'
           AND d.name = 'sng_commission_tier_0'
           AND d.model = 'sng.commission.tier'
           AND t.scheme_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM ir_model_data x
                            WHERE x.module = d.module AND x.name = 'sng_commission_scheme_default')""")

    # El tramo ya no tiene compañía y la identidad del mensual pasa a ser el cuadro.
    cr.execute("ALTER TABLE sng_commission_tier ALTER COLUMN company_id DROP NOT NULL")
    cr.execute("ALTER TABLE sng_commission_tier "
               "DROP CONSTRAINT IF EXISTS sng_commission_tier_unique_min_amount_company")
    cr.execute("ALTER TABLE sng_commission_monthly "
               "DROP CONSTRAINT IF EXISTS sng_commission_monthly_unique_salesperson_period_company")
