# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import base64
from datetime import datetime

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class SngCreditNoteExportWizard(models.TransientModel):
    """
    Wizard para exportar el reporte de Notas de Crédito a formato Excel (XLSX).

    Este wizard:
    1. Respeta los filtros activos aplicados en la vista tree
    2. Exporta todas las columnas visibles con formato profesional
    3. Genera un archivo XLSX con encabezados, formatos de fecha y moneda
    """

    _name = 'sng.credit.note.export.wizard'
    _description = 'Exportar Reporte de Notas de Crédito a Excel'

    file_data = fields.Binary('Archivo', readonly=True, attachment=False)
    file_name = fields.Char('Nombre del Archivo', readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Completado')
    ], default='draft')

    @api.model
    def default_get(self, fields_list):
        """Verificar que xlsxwriter esté disponible."""
        res = super().default_get(fields_list)
        if not xlsxwriter:
            raise UserError(
                'La librería Python "xlsxwriter" no está instalada.\n\n'
                'Por favor, instálela ejecutando:\n'
                'pip install xlsxwriter'
            )
        return res

    def action_export_xlsx(self):
        """
        Genera el archivo XLSX con los datos del reporte aplicando filtros activos.
        """
        self.ensure_one()

        # Obtener el dominio activo desde el contexto (filtros aplicados en la vista)
        active_domain = self.env.context.get('active_domain', [])
        active_ids = self.env.context.get('active_ids', [])

        # Si hay registros seleccionados manualmente, usar esos
        if active_ids:
            domain = [('id', 'in', active_ids)]
        elif active_domain:
            domain = active_domain
        else:
            # Por defecto, exportar solo publicadas
            domain = [('state', '=', 'posted')]

        # Buscar registros con el dominio aplicado
        records = self.env['sng.credit.note.report'].search(domain, order='credit_note_date desc, credit_note_number')

        if not records:
            raise UserError('No hay registros para exportar con los filtros aplicados.')

        # Crear el archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Notas de Crédito')

        # Definir formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True
        })

        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1,
            'align': 'center'
        })

        currency_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': 1,
            'align': 'right'
        })

        text_format = workbook.add_format({
            'border': 1,
            'valign': 'top',
            'text_wrap': True
        })

        # Definir encabezados (en el orden solicitado)
        headers = [
            'ID Cliente',
            'Nombre Cliente',
            'Número NC',
            'Fecha NC',
            'Monto NC',
            'Motivo',
            'Facturas Relacionadas',
            'Estado',
            'Compañía'
        ]

        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Ajustar anchos de columna
        worksheet.set_column(0, 0, 15)  # ID Cliente
        worksheet.set_column(1, 1, 30)  # Nombre Cliente
        worksheet.set_column(2, 2, 20)  # Número NC
        worksheet.set_column(3, 3, 12)  # Fecha NC
        worksheet.set_column(4, 4, 15)  # Monto NC
        worksheet.set_column(5, 5, 30)  # Motivo
        worksheet.set_column(6, 6, 40)  # Facturas Relacionadas
        worksheet.set_column(7, 7, 12)  # Estado
        worksheet.set_column(8, 8, 20)  # Compañía

        # Congelar primera fila
        worksheet.freeze_panes(1, 0)

        # Escribir datos
        row = 1
        for record in records:
            # Mapeo de estado para visualización
            state_display = {
                'draft': 'Borrador',
                'posted': 'Publicado',
                'cancel': 'Cancelado'
            }.get(record.state, record.state or '')

            worksheet.write(row, 0, record.partner_unique_id or '', text_format)
            worksheet.write(row, 1, record.partner_name or '', text_format)
            worksheet.write(row, 2, record.credit_note_number or '', text_format)

            # Fecha como fecha real de Excel
            if record.credit_note_date:
                worksheet.write_datetime(row, 3, record.credit_note_date, date_format)
            else:
                worksheet.write(row, 3, '', date_format)

            # Monto como número
            worksheet.write_number(row, 4, record.credit_note_amount or 0.0, currency_format)

            worksheet.write(row, 5, record.reason_ref or '', text_format)
            worksheet.write(row, 6, record.related_invoices or '', text_format)
            worksheet.write(row, 7, state_display, text_format)
            worksheet.write(row, 8, record.company_id.name if record.company_id else '', text_format)

            row += 1

        # Cerrar el workbook
        workbook.close()

        # Obtener el contenido del archivo
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'Notas_Credito_{timestamp}.xlsx'

        # Actualizar el wizard con el archivo generado
        self.write({
            'file_data': file_data,
            'file_name': file_name,
            'state': 'done'
        })

        # Retornar la vista del wizard con el botón de descarga
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sng.credit.note.export.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context
        }

    def action_download(self):
        """Acción para descargar el archivo generado."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=file_data&filename={self.file_name}&download=true',
            'target': 'self',
        }
