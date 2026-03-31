# -*- coding: utf-8 -*-
{
    'name': 'SNG - Ocultar Órdenes con Facturas en Vista "Pendiente por Facturar"',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': '''
        Agrega un filtro opcional (activado por defecto) para ocultar órdenes de venta
        que ya tienen al menos una factura asociada en la vista "Pendiente por facturar"
    ''',
    'description': '''
        SNG - Ocultar Órdenes con Facturas en "Pendiente por Facturar"
        =================================================================

        **Objetivo:**
        Agregar un filtro opcional en la vista "Pendiente por facturar" para que
        por defecto NO muestre órdenes de venta que ya tengan al menos una factura
        asociada, pero permitiendo al usuario ver todas las órdenes si lo necesita.

        **Funcionalidad:**

        * Agrega un campo computado booleano `has_invoice` al modelo `sale.order`
        * El campo `has_invoice` es True si la orden tiene al menos una factura asociada
        * Agrega un filtro "Sin facturas generadas" en la search view
        * El filtro está ACTIVADO por defecto mediante context
        * Usuario puede desactivar el filtro para ver todas las órdenes pendientes

        **Regla de negocio (con filtro activado por defecto):**

        * Si una orden tiene invoice_status = 'to invoice' pero YA tiene facturas,
          NO aparece en la vista (a menos que el usuario desactive el filtro)
        * Por defecto, solo aparecen órdenes pendientes SIN ninguna factura generada
        * Usuario puede desactivar el filtro para ver todas las órdenes pendientes

        **Casos de uso (filtro activado):**

        * Orden con factura parcial: NO aparece (ya tiene al menos una factura)
        * Orden con anticipo facturado: NO aparece (ya tiene al menos una factura)
        * Orden sin facturas y pendiente: SÍ aparece (cumple ambos criterios)
        * Orden totalmente facturada: NO aparece (invoice_status != 'to invoice')

        **Flexibilidad:**

        * Usuario puede desactivar el filtro "Sin facturas generadas" en cualquier momento
        * Permite revisar órdenes con facturas parciales cuando sea necesario
        * Comportamiento por defecto sigue siendo ocultar órdenes con facturas

        **Compatibilidad:**
        * Odoo 18 Community/Enterprise
        * No modifica código nativo
        * Utiliza herencia estándar de Odoo

        **Autor:** SNG Development Team
        **Licencia:** LGPL-3
    ''',
    'author': 'SNG Development Team',
    'website': 'https://www.sng.com',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'account',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Views
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
