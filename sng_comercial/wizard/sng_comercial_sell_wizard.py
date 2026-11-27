# -*- coding: utf-8 -*-
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..models.sng_comercial_sell_report import ZONA_HORARIA
from ..report import sell_in_out_xlsx


class SngComercialSellWizard(models.TransientModel):
    _name = 'sng.comercial.sell.wizard'
    _description = 'Descargar Sell in / Sell out'

    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(
        string='Hasta', required=True, default=lambda self: fields.Date.context_today(self))
    company_ids = fields.Many2many(
        'res.company', string='Compañías', required=True,
        default=lambda self: self.env.companies,
        domain=lambda self: [('id', 'in', self.env.companies.ids)])

    @api.constrains('date_from', 'date_to')
    def _check_fechas(self):
        for wizard in self:
            if wizard.date_to < wizard.date_from:
                raise ValidationError(_('La fecha final no puede ser anterior a la inicial.'))

    def _dominio_periodo(self):
        self.ensure_one()
        return [
            ('company_id', 'in', (self.company_ids & self.env.companies).ids),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

    def _meses(self):
        """Meses del periodo como «AAAA-MM», en orden."""
        mes, fin = self.date_from.replace(day=1), self.date_to.replace(day=1)
        meses = []
        while mes <= fin:
            meses.append(mes.strftime('%Y-%m'))
            mes += relativedelta(months=1)
        return meses

    def _datos(self):
        """Dict que consume ``sell_in_out_xlsx.generar``. Sale de los mismos
        modelos que se ven en pantalla, así el Excel siempre cuadra con ellos."""
        self.ensure_one()
        companias = self.company_ids & self.env.companies
        filas = {}

        def fila(company, product):
            clave = (company.id, product.id)
            if clave not in filas:
                template = product.product_tmpl_id
                filas[clave] = {
                    'compania': company.name,
                    'codigo': product.default_code or '',
                    'descripcion': product.name or '',
                    'base': template.sng_base_id.name or '',
                    'pilar': template.sng_pilar_id.name or '',
                    'volumen': template.sng_litros_unidad,
                    'stock': 0.0, 'transito': 0.0, 'bodega': 0.0,
                    'in_mes': {}, 'out_mes': {},
                    'proveedores': set(),
                }
            return filas[clave]

        Inventario = self.env['sng.comercial.inventario.report']
        for linea in Inventario.search([('company_id', 'in', companias.ids)]):
            fila(linea.company_id, linea.product_id).update(
                stock=linea.stock, transito=linea.transito, bodega=linea.bodega_grupo)

        # active_test=False: un producto archivado con movimiento en el periodo también cuenta.
        Sell = self.env['sng.comercial.sell.report'].with_context(active_test=False)
        dominio = self._dominio_periodo()
        for company, product, mes, qty_in, qty_out in Sell._read_group(
                dominio, ['company_id', 'product_id', 'date:month'], ['qty_in:sum', 'qty_out:sum']):
            destino = fila(company, product)
            clave_mes = mes.strftime('%Y-%m')
            destino['in_mes'][clave_mes] = qty_in
            destino['out_mes'][clave_mes] = qty_out
        for company, product, partner in Sell._read_group(
                dominio + [('tipo', '=', 'sell_in')], ['company_id', 'product_id', 'partner_id']):
            fila(company, product)['proveedores'].add(partner.name or '')

        ordenadas = sorted(filas.values(), key=lambda x: (x['compania'], x['pilar'], x['base'], x['descripcion']))
        for destino in ordenadas:
            destino['proveedores'] = ', '.join(sorted(destino['proveedores']))

        generado = datetime.now(ZoneInfo(ZONA_HORARIA))
        corte = 'Datos de Odoo al %s, hora de Costa Rica.' % generado.strftime('%d/%m/%Y %H:%M')
        if self.date_to >= generado.date():
            corte += ' El periodo aún no cierra.'
        return {
            'companias': ', '.join(companias.mapped('name')),
            'periodo': '%s al %s' % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y')),
            'corte': corte,
            'meses': self._meses(),
            'filas': ordenadas,
        }

    def _excel(self):
        """(nombre, contenido) del libro de Excel."""
        self.ensure_one()
        datos = self._datos()
        if not datos['filas']:
            raise UserError(_(
                'No hay productos con pilar en las compañías elegidas. Revisa en Comercial > '
                'Configuración que el atributo de pilar esté marcado y asignado a los productos.'))
        nombre = 'Sell in - Sell out %s a %s.xlsx' % (self.date_from.isoformat(), self.date_to.isoformat())
        return nombre, sell_in_out_xlsx.generar(datos)

    def action_descargar_excel(self):
        self.ensure_one()
        nombre, contenido = self._excel()
        Attachment = self.env['ir.attachment']
        # Limpia los archivos anteriores del mismo usuario para no acumular adjuntos.
        Attachment.search([
            ('res_model', '=', self._name),
            ('create_uid', '=', self.env.uid),
        ]).unlink()
        adjunto = Attachment.create({
            'name': nombre,
            'type': 'binary',
            'datas': base64.b64encode(contenido),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % adjunto.id,
            'target': 'download',
        }

    def action_ver_analisis(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('sng_comercial.action_sng_comercial_sell_report')
        action['domain'] = self._dominio_periodo()
        action['context'] = {}
        action['display_name'] = _('Sell in / Sell out · %(desde)s al %(hasta)s',
                                   desde=self.date_from.strftime('%d/%m/%Y'),
                                   hasta=self.date_to.strftime('%d/%m/%Y'))
        return action
