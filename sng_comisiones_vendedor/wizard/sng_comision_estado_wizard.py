# -*- coding: utf-8 -*-
import base64

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from ..models import libro_excel

CRUCES = [
    ('reportados', 'Reportados por el vendedor'),
    ('anulados', 'Anulados'),
    ('registrados_por_otro', 'Comisión suya, registrada por otro'),
    ('comision_de_otro', 'Registrados por él, comisión de otro'),
    ('sin_comision', 'Sin comisión'),
    ('reversos', 'Reversos'),
]


def _colones(monto):
    return '₡{:,.2f}'.format(monto or 0.0)


class SngComisionEstadoWizard(models.TransientModel):
    """Lo mismo que ve el vendedor en la app, para la oficina."""
    _name = 'sng.comision.estado.wizard'
    _description = 'Estado de comisiones del vendedor (consulta)'

    vendedor_id = fields.Many2one(
        'res.partner', string='Vendedor', required=True,
        domain="[('is_salesperson', '=', True)]")
    periodo = fields.Date(
        string='Mes', required=True,
        default=lambda self: self.env['sng.comision.estado']._hoy_cr().replace(day=1),
        help='Cualquier día del mes a consultar.')
    resumen_html = fields.Html(string='Resumen', readonly=True, sanitize=False)
    line_ids = fields.One2many('sng.comision.estado.wizard.line', 'wizard_id')
    reportados_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'reportados')])
    anulados_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'anulados')])
    registrados_por_otro_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'registrados_por_otro')])
    comision_de_otro_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'comision_de_otro')])
    sin_comision_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'sin_comision')])
    reversos_ids = fields.One2many(
        'sng.comision.estado.wizard.line', 'wizard_id', domain=[('cruce', '=', 'reversos')])

    def action_consultar(self):
        self.ensure_one()
        estado = self.env['sng.comision.estado'].obtener_estado(self.vendedor_id.id, str(self.periodo))
        self.line_ids.unlink()
        vals = []
        for cruce, _nombre in CRUCES:
            for p in estado['cruces'][cruce]['pagos']:
                vals.append(self._linea(cruce, p))
        self.env['sng.comision.estado.wizard.line'].create(vals)
        self.resumen_html = self._html(estado)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Estado de comisiones'),
        }

    def _excel(self):
        """(nombre, contenido) del libro de Excel con el estado recién
        consultado: no depende de haber dado «Consultar» antes."""
        self.ensure_one()
        estado = self.env['sng.comision.estado'].obtener_estado(self.vendedor_id.id, str(self.periodo))
        nombre = 'Estado de comisiones - %s - %s.xlsx' % (estado['vendedor']['nombre'], estado['periodo'][:7])
        return nombre, libro_excel.generar(estado)

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

    def _linea(self, cruce, p):
        if cruce == 'anulados':
            detalle = p.get('detalle', '')
            if p.get('anulado_por'):
                detalle += ' · anuló %s' % p['anulado_por']
        elif cruce == 'comision_de_otro':
            detalle = 'Comisión a %s' % p.get('comision_a', '')
        elif cruce == 'sin_comision':
            detalle = p.get('motivo', '')
        elif cruce == 'reversos':
            detalle = '%s (mes %s) · ajuste %s' % (p.get('motivo', ''), p.get('periodo_original', ''),
                                                     _colones(p.get('ajuste')))
        else:
            detalle = ''
        return {
            'wizard_id': self.id,
            'cruce': cruce,
            'payment_id': p['id'],
            'recibo': p['recibo'],
            'fecha': p['fecha'] or False,
            'fecha_confirmacion': p['fecha_confirmacion'] or False,
            'cliente': p['cliente'],
            'compania': p['compania'],
            'monto': p['monto'],
            'base': p.get('base', 0.0),
            'estado': p['estado_texto'],
            'verificado': p['verificado'],
            'registrado_por': p['registrado_por']['nombre'],
            'facturas': ', '.join(p['facturas']),
            'detalle': detalle,
        }

    @api.model
    def _html(self, estado):
        filas = Markup('')
        for r in estado['resumen']:
            # En un mes cerrado no hay siguiente tramo (no es «tramo máximo»).
            falta = libro_excel.siguiente_tramo_texto(r)
            filas += Markup(
                '<tr><td>%s</td><td>%s%s</td><td class="text-end">%s</td><td class="text-end">%s %%</td>'
                '<td class="text-end">%s</td><td class="text-end">%s</td><td class="text-end">%s</td><td>%s</td></tr>'
            ) % (r['cuadro'], r['estado_texto'], ' (estimado)' if r['estimado'] else '',
                 _colones(r['base']), r['porcentaje'], _colones(r['comision']), _colones(r['ajustes']),
                 _colones(r['en_proceso']), falta)
        # De qué compañía viene cada comisión (un cuadro puede juntar varias).
        desglose = Markup('')
        for r in estado['resumen']:
            for cia in r.get('companias') or []:
                desglose += Markup(
                    '<tr><td>%s</td><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                    '<td class="text-end">%s</td><td class="text-end">%s</td></tr>'
                ) % (r['cuadro'], cia['compania'], _colones(cia['cobrado']), _colones(cia['base']),
                     _colones(cia['comision']), _colones(cia['ajustes']))
        if desglose:
            desglose = Markup(
                '<h6>Por compañía</h6><table class="table table-sm"><thead><tr><th>Cuadro</th>'
                '<th>Compañía</th><th class="text-end">Cobrado</th><th class="text-end">Base</th>'
                '<th class="text-end">Comisión</th><th class="text-end">Ajustes</th></tr></thead>'
                '<tbody>%s</tbody></table>') % desglose
        c = estado['cruces']
        pe = c['reportados']['por_estado']
        chips = Markup(' · ').join(escape(t) for t in (
            'Reportados %s (verificados %s, sin verificar %s, no aplicados %s, anulados %s, rechazados %s)' % (
                c['reportados']['cantidad'], pe['verificado'], pe['sin_verificar'], pe['no_aplicado'],
                pe['anulado'], pe['rechazado']),
            'Anulados %s: rehechos %s, feria %s, sin reemplazo %s' % (
                c['anulados']['cantidad'], c['anulados']['rehechos'], c['anulados']['feria'],
                c['anulados']['sin_reemplazo']),
            'Registrados por otro %s (%s de base)' % (
                c['registrados_por_otro']['cantidad'], _colones(c['registrados_por_otro']['base'])),
            'Comisión de otro %s' % c['comision_de_otro']['cantidad'],
            'Sin comisión %s' % c['sin_comision']['cantidad'],
            'Reversos %s (%s)' % (c['reversos']['cantidad'], _colones(c['reversos']['ajuste'])),
        ))
        return Markup(
            '<table class="table table-sm"><thead><tr><th>Cuadro</th><th>Estado</th>'
            '<th class="text-end">Base</th><th class="text-end">Tramo</th><th class="text-end">Comisión</th>'
            '<th class="text-end">Ajustes</th><th class="text-end">En proceso</th><th>Siguiente tramo</th>'
            '</tr></thead><tbody>%s</tbody></table>%s<p>%s</p>'
        ) % (filas, desglose, chips)


class SngComisionEstadoWizardLine(models.TransientModel):
    _name = 'sng.comision.estado.wizard.line'
    _description = 'Pago del estado de comisiones'
    _order = 'fecha desc, id desc'

    wizard_id = fields.Many2one('sng.comision.estado.wizard', required=True, ondelete='cascade')
    cruce = fields.Selection(CRUCES, required=True)
    payment_id = fields.Many2one('account.payment', string='Pago')
    recibo = fields.Char(string='Recibo')
    fecha = fields.Date(string='Fecha')
    fecha_confirmacion = fields.Date(string='Confirmado')
    cliente = fields.Char(string='Cliente')
    compania = fields.Char(string='Compañía')
    monto = fields.Float(string='Monto', digits=(16, 2))
    base = fields.Float(string='Base comisión', digits=(16, 2))
    estado = fields.Char(string='Estado')
    verificado = fields.Boolean(string='Verificado')
    registrado_por = fields.Char(string='Registrado por')
    facturas = fields.Char(string='Facturas')
    detalle = fields.Char(string='Detalle')
