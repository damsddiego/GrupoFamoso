# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.tools.misc import xlwt
import io
import base64


class Inventory_ABC_analysis_wizard(models.Model):
    _name = 'inventory.abc.report.wiz'
    _description = 'Inventory abc Analysis Report'

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    company_ids = fields.Many2many("res.company", string="Company")
    category_ids = fields.Many2many(
        "product.category", string="Product Category")
    product_ids = fields.Many2many("product.product", string="Product")
    type = fields.Selection([('all', 'All'),
        ('high_stock', 'A Class'),
        ('medium_stock', 'B Class'),
        ('low_stock', 'C Class')], "Classification For ABC", default="all")

    def print_inventory_ABC_report(self):

        filename = 'Stock ABC Report' + '.xls'
        workbook = xlwt.Workbook()

        worksheet = workbook.add_sheet('Stock ABC Report')
        font = xlwt.Font()
        font.bold = True
        for_left = xlwt.easyxf(
            "font: bold 1, color black; borders: top double, bottom double, left double, right double; align: horiz left")
        for_left_not_bold = xlwt.easyxf(
            "font: color black; align: horiz left", num_format_str='0.00')

        GREEN_TABLE_HEADER = xlwt.easyxf(
            'font: bold 1, name Tahoma, height 250;'
            'align: vertical center, horizontal center, wrap on;'
            'borders: top double, bottom double, left double, right double;'
        )
        style = xlwt.easyxf(
            'font:height 400, bold True, name Arial; align: horiz center, vert center;borders: top medium,right medium,bottom medium,left medium')

        alignment = xlwt.Alignment()  # Create Alignment
        alignment.horz = xlwt.Alignment.HORZ_RIGHT
        style = xlwt.easyxf('align: wrap yes')
        style.num_format_str = '0.00'

        worksheet.row(0).height = 500
        worksheet.col(0).width = 10000
        worksheet.col(1).width = 7000
        worksheet.col(2).width = 4000
        worksheet.col(3).width = 4000
        worksheet.col(4).width = 4000
        worksheet.col(5).width = 4000
        worksheet.col(6).width = 4000
        worksheet.col(7).width = 4000

        worksheet.write_merge(0, 0, 0, 5, 'Stock ABC Report', GREEN_TABLE_HEADER)

        row = 2
        col = 0
        worksheet.write(row, col, 'Company' or '', for_left)
        col = 1
        if self.company_ids:
            company = self.company_ids.mapped('name')
            worksheet.write(row, col, ', '.join(company) or '', for_left_not_bold)
            col += 1

        row = 3

        worksheet.write(row, 0, 'Report Start Date' or '', for_left)
        worksheet.write(row, 1, self.from_date.strftime('%d-%m-%Y') or '', for_left)
        row = 4
        worksheet.write(row, 0, 'Report End Date' or '', for_left)
        worksheet.write(row, 1, self.to_date.strftime('%d-%m-%Y') or '', for_left)

        row = 5

        worksheet.write(row, 0, 'Product Name' or '', for_left)
        worksheet.write(row, 1, 'Category' or '', for_left)
        worksheet.write(row, 2, 'Annual num of unit sold' or '', for_left)
        worksheet.write(row, 3, 'Standard Cost' or '', for_left)
        worksheet.write(row, 4, 'Annual Consumption Value' or '', for_left)
        worksheet.write(row, 5, '(%) Of Annual Sold' or '', for_left)
        worksheet.write(row, 6, '(%) Of Annual Consumption Value' or '', for_left)
        worksheet.write(row, 7, 'ABC Classification' or '', for_left)

        rows = 6

        domain = []

        if self.category_ids:
            domain += [('categ_id', 'in', self.category_ids.ids)]

        if self.product_ids:
            domain += [('id', 'in', self.product_ids.ids)]

        product_ids = self.env['product.product'].search(domain, order='stock_value')

        location_id = self.env['stock.location']

        location_domain = [('usage', 'in', ['internal'])]

        domain = []
            
        if self.company_ids:
            domain += [('company_id','in',self.company_ids.ids)]
            location_domain += [('company_id','in',self.company_ids.ids)]

        location_id = self.env['stock.location'].search(location_domain)
        
        domain += [('location_id', 'in', location_id.ids)]
        domain += [('state','=','done')]

        date_start = self.from_date
        date_end = self.to_date

        domain += [('date','>',date_start),('date','<=',date_end)]

        total_move_lines = self.env['stock.move.line'].search(domain)
        total_sale_qty = sum(total_move_lines.mapped('quantity'))
        total_cumulative = sum(line.quantity * line.product_id.standard_price for line in total_move_lines)

        for product in product_ids:

            domain = [('product_id','=',product.id)]
            location_domain = [('usage', 'in', ['internal'])]
            
            if self.company_ids:
                domain += [('company_id','in',self.company_ids.ids)]
                location_domain += [('company_id','in',self.company_ids.ids)]

            location_id = self.env['stock.location'].search(location_domain)
            
            domain += [('location_id', 'in', location_id.ids)]
            domain += [('state','=','done')]

            date_start = self.from_date
            date_end = self.to_date

            domain += [('date','>',date_start),('date','<=',date_end)]

            move_lines = self.env['stock.move.line'].search(domain)
            
            unit_sold = sum(move_lines.mapped('quantity'))

            consumption_value_per = unit_sold * product.standard_price

            sold_value_percentage = (unit_sold/(total_sale_qty or 1))*100

            annual_consumption_percentage = (consumption_value_per/(total_cumulative or 1))*100

            if annual_consumption_percentage > 80:
                analysis_type = 'A Class'
            elif annual_consumption_percentage >= 5 and annual_consumption_percentage <= 80:
                analysis_type = 'B Class'
            elif annual_consumption_percentage < 5:
                analysis_type = 'C Class'

            if self.type == 'all':
                pass
            elif self.type == 'high_stock' and analysis_type != 'A Class':
                continue
            elif self.type == 'medium_stock' and analysis_type != 'B Class':
                continue
            elif self.type == 'low_stock' and analysis_type != 'C Class':
                continue

            worksheet.write(rows, 0, product.display_name or '', for_left_not_bold)
            worksheet.write(rows, 1, product.categ_id.display_name or '', for_left_not_bold)
            worksheet.write(rows, 2, unit_sold or '0.0',for_left_not_bold)
            worksheet.write(rows, 3, product.standard_price or '0.0', for_left_not_bold)
            worksheet.write(rows, 4, consumption_value_per or '0.0', for_left_not_bold)
            worksheet.write(rows, 5, abs(sold_value_percentage) or '0.0', for_left_not_bold)
            worksheet.write(rows, 6, annual_consumption_percentage or '0.0', for_left_not_bold)
            worksheet.write(rows, 7, analysis_type or '0.0', for_left_not_bold)

            rows += 1

        fp = io.BytesIO()
        workbook.save(fp)
        abc_id = self.env['inventory.abc.extended'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        fp.close()

        return {
            'view_mode': 'form',
            'res_id': abc_id.id,
            'res_model': 'inventory.abc.extended',
            'type': 'ir.actions.act_window',
            'context': self._context,
            'target': 'new',
        }

    def tree_graph_report_view(self):
        record_set = self.env['inventory.abc.extended'].search([])
        record_set.unlink()

        total_value = 0.0
        consumption_value_per = 0.0
        analysis_type = ''
        value = 0
        sold_value_percentage = 0.0

        total_cumulative = 0.0
        annual_consumption_percentage = 0.0
        inv_obj = self.env['inventory.abc.extended']

        domain = []

        if self.category_ids:
            domain += [('categ_id', 'in', self.category_ids.ids)]

        if self.product_ids:
            domain += [('id', 'in', self.product_ids.ids)]

        product_ids = self.env['product.product'].search(domain, order='stock_value')

        location_id = self.env['stock.location']

        location_domain = [('usage', 'in', ['internal'])]

        domain = []
            
        if self.company_ids:
            domain += [('company_id','in',self.company_ids.ids)]
            location_domain += [('company_id','in',self.company_ids.ids)]

        location_id = self.env['stock.location'].search(location_domain)
        
        domain += [('location_id', 'in', location_id.ids)]
        domain += [('state','=','done')]

        date_start = self.from_date
        date_end = self.to_date

        domain += [('date','>',date_start),('date','<=',date_end)]

        total_move_lines = self.env['stock.move.line'].search(domain)
        total_sale_qty = sum(total_move_lines.mapped('quantity'))
        total_cumulative = sum(line.quantity * line.product_id.standard_price for line in total_move_lines)

        for product in product_ids:

            domain = [('product_id','=',product.id)]
            location_domain = [('usage', 'in', ['internal'])]
            
            if self.company_ids:
                domain += [('company_id','in',self.company_ids.ids)]
                location_domain += [('company_id','in',self.company_ids.ids)]

            location_id = self.env['stock.location'].search(location_domain)
            
            domain += [('location_id', 'in', location_id.ids)]
            domain += [('state','=','done')]

            date_start = self.from_date
            date_end = self.to_date

            domain += [('date','>',date_start),('date','<=',date_end)]

            move_lines = self.env['stock.move.line'].search(domain)
            
            unit_sold = sum(move_lines.mapped('quantity'))

            consumption_value_per = unit_sold * product.standard_price

            sold_value_percentage = (unit_sold/(total_sale_qty or 1))*100
            annual_consumption_percentage = (consumption_value_per/(total_cumulative or 1))*100

            if annual_consumption_percentage > 80:
                analysis_type = 'A Class'
            elif annual_consumption_percentage >= 5 and annual_consumption_percentage <= 80:
                analysis_type = 'B Class'
            elif annual_consumption_percentage < 5:
                analysis_type = 'C Class'

            if self.type == 'all':
                pass
            elif self.type == 'high_stock' and analysis_type != 'A Class':
                continue
            elif self.type == 'medium_stock' and analysis_type != 'B Class':
                continue
            elif self.type == 'low_stock' and analysis_type != 'C Class':
                continue

            inv_obj.create({
                'products': product.id,
                'product_category': product.categ_id.id,
                'company': self.env.user.company_id.id,
                'unit_sold': unit_sold,
                'value': product.standard_price,
                'sold_value_percentage': abs(sold_value_percentage),
                'annual_consumption_percentage': annual_consumption_percentage,
                'consumption_value_per': consumption_value_per,
                'analysis_type': analysis_type,
            })

        display = []
        graph_id = self.env.ref('bi_abc_analysis_report.inventory_abc_extended_report_graph').id
        tree_id = self.env.ref('bi_abc_analysis_report.inventory_abc_extended_report_tree').id

        graph_first = self.env.context.get('report_graph', False)

        if graph_first:
            display.append((graph_id, 'graph'))
            display.append((tree_id, 'list'))
        else:
            display.append((tree_id, 'list'))
            display.append((graph_id, 'graph'))
        return {
            'name': _('Stock ABC Ratio Analysis'),
            'res_model': 'inventory.abc.extended',
            'view_mode': 'list',
            'type': 'ir.actions.act_window',
            'views': display,
        }


class Inventory_ABC_analysis_Extended(models.TransientModel):
    _name = 'inventory.abc.extended'
    _description = "Stock abc Excel Extended"

    excel_file = fields.Binary('Download Report :- ')
    file_name = fields.Char('Excel File', size=64)

    products = fields.Many2one("product.product", "Product")
    product_category = fields.Many2one("product.category", "Category")
    company = fields.Many2one("res.company", "Company")
    unit_sold = fields.Float("Annual Unit Sold")
    value = fields.Float("Standard Cost")
    sold_value_percentage = fields.Float("(%) Of Annual Sold")
    annual_consumption_percentage = fields.Float(
        "(%) Of Annual Consumption Value")
    consumption_value_per = fields.Float("Annual Consumption Value")
    analysis_type = fields.Char("Classification For ABC")
    wizard_id = fields.Many2one("inventory.abc.report.wiz")


class Inherit_product_product(models.Model):
    _inherit = 'product.product'

    stock_value = fields.Float(
        "Stock Value", 
        compute='calculate_stock_value', 
        store=True 
    )

    @api.depends('standard_price', 'qty_available')
    def calculate_stock_value(self):
        for product in self:
            product.stock_value = product.standard_price * product.qty_available if product.standard_price and product.qty_available else 0.0
