from odoo import api, fields, models


class GfBodegaRegistro(models.Model):
    """Un bloque de trabajo de un empleado de bodega, registrado por la app GF.

    Los nombres técnicos de este modelo y de sus campos los usa la app Android
    (data/odoo/OdooApi.kt): no cambiarlos sin actualizar la app.
    """

    _name = 'gf.bodega.registro'
    _description = 'Registro de trabajo de bodega'
    _order = 'fecha_inicio desc, id desc'

    empleado_nombre = fields.Char(string='Empleado', required=True, index=True)
    empleado_key = fields.Char(
        string='ID de empleado',
        index=True,
        help='Key del empleado en Firebase. No cambia aunque se cambie el nombre.',
    )
    dispositivo = fields.Char(string='Tableta', index=True)

    tipo = fields.Selection(
        selection=[('alistado', 'Alistado'), ('actividad', 'Actividad')],
        string='Tipo',
        required=True,
        index=True,
    )
    actividad_id = fields.Many2one(
        comodel_name='gf.bodega.actividad',
        string='Actividad',
        ondelete='restrict',
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Orden de venta',
        ondelete='set null',
        index=True,
    )
    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Entrega',
        ondelete='set null',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        related='sale_order_id.company_id',
        store=True,
        readonly=True,
    )

    fecha_inicio = fields.Datetime(
        string='Inicio',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    fecha_fin = fields.Datetime(string='Fin')
    duracion_min = fields.Float(
        string='Duración (min)',
        compute='_compute_duracion_min',
        store=True,
        digits=(16, 1),
    )

    estado = fields.Selection(
        selection=[
            ('en_curso', 'En curso'),
            ('validado', 'Validado'),
            ('abandonado', 'Abandonado'),
            ('finalizado', 'Finalizado'),
        ],
        string='Estado',
        required=True,
        default='en_curso',
        index=True,
    )

    lineas = fields.Integer(string='Líneas alistadas')
    unidades_pedidas = fields.Float(string='Unidades pedidas')
    unidades_entregadas = fields.Float(string='Unidades entregadas')

    @api.depends('fecha_inicio', 'fecha_fin')
    def _compute_duracion_min(self):
        for registro in self:
            if registro.fecha_inicio and registro.fecha_fin:
                delta = registro.fecha_fin - registro.fecha_inicio
                registro.duracion_min = max(delta.total_seconds(), 0.0) / 60.0
            else:
                registro.duracion_min = 0.0

    @api.depends('empleado_nombre', 'tipo', 'sale_order_id', 'actividad_id')
    def _compute_display_name(self):
        for registro in self:
            if registro.tipo == 'alistado':
                detalle = registro.sale_order_id.name or 'Alistado'
            else:
                detalle = registro.actividad_id.name or 'Actividad'
            registro.display_name = f'{registro.empleado_nombre or ""} - {detalle}'
