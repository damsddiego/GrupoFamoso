# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StockAdjustmentRequest(models.Model):
    _name = 'stock.adjustment.request'
    _description = 'Solicitud de Ajuste de Inventario'
    _inherit = ['mail.thread']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Número',
        required=True,
        readonly=True,
        default=lambda self: _('Nuevo'),
        copy=False,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('submitted', 'Enviado'),
            ('approved', 'Aprobado'),
            ('rejected', 'Rechazado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        readonly=True,
        copy=False,
    )
    request_date = fields.Datetime(
        string='Fecha de Solicitud',
        default=fields.Datetime.now,
        readonly=True,
    )
    approval_date = fields.Datetime(
        string='Fecha de Aprobación',
        readonly=True,
        copy=False,
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Solicitado por',
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    reason = fields.Char(
        string='Referencia / Razón',
        help='Se utilizará como referencia en los movimientos de inventario generados.',
    )
    notes = fields.Text(
        string='Notas',
    )
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many(
        'stock.adjustment.request.line',
        'request_id',
        string='Líneas de Ajuste',
        copy=True,
    )
    move_count = fields.Integer(
        string='Movimientos',
        compute='_compute_move_count',
    )

    @api.depends('line_ids.move_ids')
    def _compute_move_count(self):
        for req in self:
            req.move_count = len(req.line_ids.mapped('move_ids'))

    # ------------------------------------------------------------------
    # Secuencia
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'stock.adjustment.request'
                ) or _('Nuevo')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_submit(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Debe agregar al menos una línea de ajuste.'))
        for line in self.line_ids:
            line._validate_for_submission()
            line._snapshot_quantity()
        self.write({'state': 'submitted'})
        self.message_post(body=_('Solicitud enviada para aprobación.'))

    def action_approve(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'stock_adjustment_approval.group_stock_adjustment_approver'
        ):
            raise UserError(
                _('Solo los usuarios del grupo "Aprobador de Ajuste de Inventario" pueden aprobar solicitudes.')
            )
        if self.state != 'submitted':
            raise UserError(_('Solo se pueden aprobar solicitudes en estado "Enviado".'))
        if not self.line_ids:
            raise UserError(_('No hay líneas para aprobar.'))

        for line in self.line_ids:
            line._apply_adjustment()

        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Solicitud aprobada y ajustes aplicados por %s.') % self.env.user.name,
        )

    def action_reject(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Solo se pueden rechazar solicitudes en estado "Enviado".'))
        return {
            'name': _('Rechazar Solicitud'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.adjustment.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_cancel(self):
        self.ensure_one()
        if self.state in ('approved',):
            raise UserError(_('No se puede cancelar una solicitud ya aprobada.'))
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.ensure_one()
        if self.state not in ('rejected', 'cancelled'):
            raise UserError(_('Solo se pueden devolver a borrador solicitudes rechazadas o canceladas.'))
        self.write({'state': 'draft', 'rejection_reason': False})

    def action_view_moves(self):
        self.ensure_one()
        moves = self.line_ids.mapped('move_ids')
        return {
            'name': _('Movimientos de Inventario'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'stock.move',
            'domain': [('id', 'in', moves.ids)],
            'context': dict(self.env.context),
        }


class StockAdjustmentRequestLine(models.Model):
    _name = 'stock.adjustment.request.line'
    _description = 'Línea de Solicitud de Ajuste'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'stock.adjustment.request',
        string='Solicitud',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    state = fields.Selection(
        related='request_id.state',
        string='Estado',
        readonly=True,
        store=True,
    )
    company_id = fields.Many2one(
        related='request_id.company_id',
        string='Compañía',
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain=[('is_storable', '=', True)],
        check_company=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        required=True,
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote / Serie',
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        check_company=True,
    )
    package_id = fields.Many2one(
        'stock.quant.package',
        string='Paquete',
        check_company=True,
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Propietario',
        check_company=True,
    )

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        related='product_id.uom_id',
        readonly=True,
    )
    current_quantity = fields.Float(
        string='Cantidad Actual',
        compute='_compute_current_quantity',
        readonly=True,
        digits='Product Unit of Measure',
    )
    theoretical_quantity = fields.Float(
        string='Cantidad Teórica (al enviar)',
        readonly=True,
        digits='Product Unit of Measure',
        copy=False,
    )
    counted_quantity = fields.Float(
        string='Cantidad Contada',
        required=True,
        digits='Product Unit of Measure',
        default=0.0,
    )
    difference = fields.Float(
        string='Diferencia',
        compute='_compute_difference',
        readonly=True,
        digits='Product Unit of Measure',
    )
    applied = fields.Boolean(
        string='Aplicado',
        readonly=True,
        copy=False,
    )
    move_ids = fields.Many2many(
        'stock.move',
        'stock_adjustment_request_line_stock_move_rel',
        'line_id',
        'move_id',
        string='Movimientos Generados',
        readonly=True,
        copy=False,
    )

    # ------------------------------------------------------------------
    # Onchanges / Constraints
    # ------------------------------------------------------------------
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.lot_id = False
            if not self.location_id:
                warehouse = self.env['stock.warehouse'].search(
                    [('company_id', '=', self.company_id.id or self.env.company.id)],
                    limit=1,
                )
                if warehouse:
                    self.location_id = warehouse.lot_stock_id

    @api.constrains('counted_quantity')
    def _check_counted_quantity_positive(self):
        for line in self:
            if line.counted_quantity < 0:
                raise ValidationError(
                    _('La cantidad contada no puede ser negativa. Producto: %s') % line.product_id.display_name
                )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('product_id', 'location_id', 'lot_id', 'package_id', 'owner_id')
    def _compute_current_quantity(self):
        for line in self:
            if not line.product_id or not line.location_id:
                line.current_quantity = 0.0
                continue
            quant = self.env['stock.quant']._gather(
                line.product_id,
                line.location_id,
                lot_id=line.lot_id,
                package_id=line.package_id,
                owner_id=line.owner_id,
                strict=True,
            )
            line.current_quantity = sum(quant.mapped('quantity'))

    @api.depends('current_quantity', 'counted_quantity')
    def _compute_difference(self):
        for line in self:
            line.difference = line.counted_quantity - line.current_quantity

    # ------------------------------------------------------------------
    # Lógica de aplicación
    # ------------------------------------------------------------------
    def _validate_for_submission(self):
        self.ensure_one()
        if not self.product_id or not self.location_id:
            raise UserError(_('Todas las líneas deben tener producto y ubicación.'))
        if self.product_id.tracking in ('lot', 'serial') and not self.lot_id:
            raise UserError(
                _('El producto %s requiere lote/número de serie. Por favor asígnelo.') % self.product_id.display_name
            )

    def _snapshot_quantity(self):
        self.ensure_one()
        self.theoretical_quantity = self.current_quantity

    def _apply_adjustment(self):
        self.ensure_one()
        if self.applied:
            return

        Quant = self.env['stock.quant']
        quant = Quant._gather(
            self.product_id,
            self.location_id,
            lot_id=self.lot_id,
            package_id=self.package_id,
            owner_id=self.owner_id,
            strict=True,
        )
        if quant:
            quant = quant[0]
        else:
            quant = Quant.with_context(inventory_mode=True).create({
                'product_id': self.product_id.id,
                'location_id': self.location_id.id,
                'lot_id': self.lot_id.id,
                'package_id': self.package_id.id,
                'owner_id': self.owner_id.id,
            })

        inventory_name = self.request_id.reason or _('Solicitud %s') % self.request_id.name

        last_move = self.env['stock.move'].search([], order='id desc', limit=1)
        last_move_id = last_move.id if last_move else 0

        quant = quant.with_context(inventory_name=inventory_name)
        quant.inventory_quantity = self.counted_quantity
        quant._apply_inventory()

        new_moves = self.env['stock.move'].search([
            ('id', '>', last_move_id),
            ('product_id', '=', self.product_id.id),
            ('is_inventory', '=', True),
        ])
        if new_moves:
            self.move_ids = [(6, 0, new_moves.ids)]

        self.applied = True
