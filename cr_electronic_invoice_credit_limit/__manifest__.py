{
    'name': 'CR Electronic Invoice Credit Limit',
    'version': '18.0.2.0.0',
    'category': 'Accounting',
    'summary': 'Limit credit notes amount based on original invoice',
    'description': """
        This module extends the Costa Rican Electronic Invoice module to limit
        the creation of credit notes so that their total amount doesn't exceed
        the original invoice amount.

        Control de notas de crédito de cliente: la nota de crédito hecha desde
        la factura no mueve inventario; si la mercadería regresa, el asistente
        abre una devolución (sng_return) y la nota de crédito se genera desde
        ahí al recibirla. «Anular y refacturar» crea la nota de crédito código
        01 y deja la factura sustituta en borrador, ligada a la misma orden.
        Motivo de anulación obligatorio y lista «Control de anulaciones».
    """,
    'author': 'SNG',
    'website': 'https://www.sngcloud.com',
    'depends': ['cr_electronic_invoice', 'stock', 'sale_stock', 'sng_return'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sng_motivo_anulacion_data.xml',
        'views/account_move_views.xml',
        'views/account_move_reversal_views.xml',
        'views/sng_control_anulaciones_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}