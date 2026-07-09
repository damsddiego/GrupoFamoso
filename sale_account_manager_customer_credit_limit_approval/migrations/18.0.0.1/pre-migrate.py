# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        SELECT id::text
          FROM res_company
         ORDER BY id
        """
    )
    company_ids = [row[0] for row in cr.fetchall()]
    if not company_ids:
        return

    field_names = [
        'credit_check',
        'credit_warning',
        'credit_blocking',
    ]

    for field_name in field_names:
        cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'res_partner'
               AND column_name = %s
            """,
            [field_name],
        )
        row = cr.fetchone()
        if not row or row[0] == 'jsonb':
            continue

        pairs_sql = ', '.join(
            "'%s', %s" % (company_id, field_name)
            for company_id in company_ids
        )

        cr.execute(
            f"""
            ALTER TABLE res_partner
            ALTER COLUMN {field_name} TYPE jsonb
            USING CASE
                WHEN {field_name} IS NULL THEN NULL
                ELSE jsonb_build_object({pairs_sql})
            END
            """,
        )
