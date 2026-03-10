# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import openpyxl
from io import BytesIO


class ImportPurchaseLinesWizard(models.TransientModel):
    _name = 'import.purchase.lines.wizard'
    _description = 'Import Purchase Lines Wizard'

    file = fields.Binary(string='Excel File', required=True, help='Upload Excel file with purchase lines')
    filename = fields.Char(string='Filename')

    def action_import(self):
        """Import purchase order lines from Excel file"""
        self.ensure_one()

        if not self.file:
            raise UserError(_('Please upload an Excel file.'))

        # Get the purchase order from context
        purchase_order_id = self.env.context.get('active_id')
        if not purchase_order_id:
            raise UserError(_('No purchase order found in context.'))

        purchase_order = self.env['purchase.order'].browse(purchase_order_id)

        # Decode the file
        try:
            file_content = base64.b64decode(self.file)
            workbook = openpyxl.load_workbook(BytesIO(file_content))
            sheet = workbook.active
        except Exception as e:
            raise UserError(_('Error reading Excel file: %s') % str(e))

        # Read data from Excel
        lines_data = []
        errors = []
        row_number = 1

        for row in sheet.iter_rows(min_row=2, values_only=True):  # Skip header row
            row_number += 1

            if not row or not any(row):  # Skip empty rows
                continue

            # Extract data from columns
            # Column mapping: codigo | NOMBRE | CANTIDAD | COSTO_unit | totalcompra | precio
            codigo = row[0]
            cantidad = row[2]
            costo_unit = row[3]
            precio_venta = row[5]

            # Validate required fields
            if not codigo:
                errors.append(_('Row %s: Missing product code') % row_number)
                continue

            if not cantidad or cantidad <= 0:
                errors.append(_('Row %s: Invalid quantity for product %s') % (row_number, codigo))
                continue

            if not costo_unit or costo_unit < 0:
                errors.append(_('Row %s: Invalid unit cost for product %s') % (row_number, codigo))
                continue

            if precio_venta is None or precio_venta < 0:
                errors.append(_('Row %s: Invalid sale price for product %s') % (row_number, codigo))
                continue

            # Search for product by default_code
            product = self.env['product.product'].search([('default_code', '=', str(codigo))], limit=1)

            if not product:
                errors.append(_('Row %s: Product with code "%s" not found') % (row_number, codigo))
                continue

            lines_data.append({
                'product': product,
                'quantity': cantidad,
                'price_unit': costo_unit,
                'sale_price': precio_venta,
            })

        # If there are errors, stop and show them
        if errors:
            error_message = _('Import failed. Please fix the following errors:\n\n')
            error_message += '\n'.join(errors)
            raise UserError(error_message)

        if not lines_data:
            raise UserError(_('No valid lines found in the Excel file.'))

        # Create purchase order lines and update product prices
        created_lines = 0
        for line_data in lines_data:
            product = line_data['product']

            # Update product sale price and cost
            product.write({
                'list_price': line_data['sale_price'],
                'standard_price': line_data['price_unit'],
            })

            # Create purchase order line
            self.env['purchase.order.line'].create({
                'order_id': purchase_order.id,
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': line_data['quantity'],
                'price_unit': line_data['price_unit'],
                'product_uom': product.uom_po_id.id,
                'date_planned': purchase_order.date_planned or fields.Datetime.now(),
            })
            created_lines += 1

        # Show success notification and close wizard
        message = _('%s lines imported successfully!') % created_lines
        purchase_order.message_post(body=message)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'notification_info': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                }
            }
        }
