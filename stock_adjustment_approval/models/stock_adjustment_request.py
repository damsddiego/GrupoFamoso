# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from .stock_quant import CLAVE_SOLICITUD_APROBADA, SOLICITUD_APROBADA


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
    # Obligatorio al enviar, no en la base: hay solicitudes viejas sin motivo.
    reason = fields.Char(
        string='Motivo',
        help='Por qué se ajusta el inventario. Es obligatorio para enviar la solicitud '
             'y se usa como referencia en los movimientos de inventario generados.',
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
    stock_changed = fields.Boolean(
        string='Stock cambió desde el envío',
        compute='_compute_stock_changed',
    )

    @api.depends('line_ids.move_ids')
    def _compute_move_count(self):
        for req in self:
            req.move_count = len(req.line_ids.mapped('move_ids'))

    @api.depends('line_ids.stock_changed')
    def _compute_stock_changed(self):
        for req in self:
            req.stock_changed = any(req.line_ids.mapped('stock_changed'))

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
        if not (self.reason or '').strip():
            raise UserError(_('Escriba el motivo del ajuste antes de enviar la solicitud.'))
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
        # Ningún ajuste de inventario lo hace una sola persona.
        if self.env.uid != SUPERUSER_ID and self.env.user in (self.create_uid | self.requested_by):
            raise UserError(
                _('Esta solicitud la tiene que aprobar otra persona: la pidió %s.')
                % (self.requested_by or self.create_uid).name
            )
        if not self.line_ids:
            raise UserError(_('No hay líneas para aprobar.'))

        changed = self.line_ids.filtered('stock_changed')
        changed_notes = [
            _('%(product)s: teórico al enviar %(theoretical)s, stock al aprobar %(current)s, se aplica %(adjustment)s')
            % {
                'product': line.product_id.display_name,
                'theoretical': line.theoretical_quantity,
                'current': line.current_quantity,
                'adjustment': line.adjustment_quantity,
            }
            for line in changed
        ]
        for line in self.line_ids:
            line._apply_adjustment()

        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        body = _('Solicitud aprobada y ajustes aplicados por %s.') % self.env.user.name
        if changed_notes:
            body = Markup('%s<br/>%s<ul>%s</ul>') % (
                body,
                _('El stock cambió entre el envío y la aprobación; se aplicó el ajuste sobre el stock actual:'),
                Markup().join(Markup('<li>%s</li>') % note for note in changed_notes),
            )
        self.message_post(body=body)

    def action_refresh_quantities(self):
        """Recarga el formulario para recalcular el stock actual de las líneas."""
        self.ensure_one()
        return True

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
    adjustment_quantity = fields.Float(
        string='Ajuste (+/-)',
        required=True,
        digits='Product Unit of Measure',
        default=0.0,
        help='Lo que se suma o resta al stock: -5 resta cinco unidades, 1 suma una. '
             'Es lo que se aplica al aprobar, sobre el stock que haya ese día.',
    )
    counted_quantity = fields.Float(
        string='Cantidad Resultante (al enviar)',
        readonly=True,
        copy=False,
        digits='Product Unit of Measure',
        help='Teórico al enviar + ajuste. Se conserva para los reportes.',
    )
    projected_quantity = fields.Float(
        string='Quedará en',
        compute='_compute_projected_quantity',
        readonly=True,
        digits='Product Unit of Measure',
        help='Stock actual + ajuste: cómo queda la ubicación si se aprueba ahora.',
    )
    stock_changed = fields.Boolean(
        string='Stock cambió',
        compute='_compute_projected_quantity',
        help='El stock actual ya no es el teórico que se tomó al enviar.',
    )
    quantity_at_approval = fields.Float(
        string='Stock al Aprobar',
        readonly=True,
        copy=False,
        digits='Product Unit of Measure',
    )
    applied_difference = fields.Float(
        string='Diferencia Aplicada',
        readonly=True,
        copy=False,
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
    @api.onchange('product_id', 'location_id', 'package_id', 'owner_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self._origin.product_id != self.product_id:
                self.lot_id = False
            if not self.location_id:
                warehouse = self.env['stock.warehouse'].search(
                    [('company_id', '=', self.company_id.id or self.env.company.id)],
                    limit=1,
                )
                if warehouse:
                    self.location_id = warehouse.lot_stock_id
            if not self.lot_id:
                self._assign_unique_existing_lot()

    def _assign_unique_existing_lot(self):
        """Select the lot automatically when the stock dimension is unambiguous."""
        self.ensure_one()
        if (
            not self.product_id
            or not self.location_id
            or self.product_id.tracking not in ('lot', 'serial')
            or self.lot_id
        ):
            return self.lot_id

        company = self.company_id or self.env.company
        quants = self.env['stock.quant'].with_company(company).search([
            ('product_id', '=', self.product_id.id),
            ('location_id', '=', self.location_id.id),
            ('lot_id', '!=', False),
            ('package_id', '=', self.package_id.id or False),
            ('owner_id', '=', self.owner_id.id or False),
        ])
        lots = quants.lot_id
        if len(lots) == 1:
            self.lot_id = lots
        return self.lot_id

    @api.constrains('request_id', 'product_id', 'location_id', 'lot_id', 'package_id', 'owner_id')
    def _check_unique_stock_key(self):
        for line in self:
            key = line._stock_key()
            if any(other != line and other._stock_key() == key for other in line.request_id.line_ids):
                raise ValidationError(
                    _('El producto %(product)s está repetido en la solicitud para la ubicación %(location)s. '
                      'Deje una sola línea con la cantidad contada.')
                    % {
                        'product': line.product_id.display_name,
                        'location': line.location_id.display_name,
                    }
                )

    def _stock_key(self):
        self.ensure_one()
        return (self.product_id, self.location_id, self.lot_id, self.package_id, self.owner_id)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('product_id', 'location_id', 'lot_id', 'package_id', 'owner_id')
    def _compute_current_quantity(self):
        for line in self:
            if not line.product_id or not line.location_id:
                line.current_quantity = 0.0
                continue
            line.current_quantity = sum(line._get_quants().mapped('quantity'))

    @api.depends('current_quantity', 'adjustment_quantity', 'theoretical_quantity', 'state')
    def _compute_projected_quantity(self):
        for line in self:
            rounding = line.product_id.uom_id.rounding or 0.01
            line.projected_quantity = line.current_quantity + line.adjustment_quantity
            line.stock_changed = line.state == 'submitted' and float_compare(
                line.current_quantity, line.theoretical_quantity, precision_rounding=rounding,
            ) != 0

    def _get_quants(self):
        """Quants exactos de la línea. `_gather(strict=True)` con lote también devuelve
        los quants sin lote de la ubicación, así que se filtran por el lote de la línea."""
        self.ensure_one()
        quants = self.env['stock.quant']._gather(
            self.product_id,
            self.location_id,
            lot_id=self.lot_id,
            package_id=self.package_id,
            owner_id=self.owner_id,
            strict=True,
        )
        return quants.filtered(lambda q: q.lot_id == self.lot_id)

    # ------------------------------------------------------------------
    # Lógica de aplicación
    # ------------------------------------------------------------------
    def _validate_for_submission(self):
        self.ensure_one()
        if not self.product_id or not self.location_id:
            raise UserError(_('Todas las líneas deben tener producto y ubicación.'))
        if not self.lot_id:
            self._assign_unique_existing_lot()
        if self.product_id.tracking in ('lot', 'serial') and not self.lot_id:
            raise UserError(
                _('El producto %s requiere lote/número de serie. Por favor asígnelo.') % self.product_id.display_name
            )
        rounding = self.product_id.uom_id.rounding
        if float_is_zero(self.adjustment_quantity, precision_rounding=rounding):
            raise UserError(
                _('El ajuste de %s es 0. Escriba cuánto suma (1) o resta (-1).') % self.product_id.display_name
            )
        self._check_result_not_negative(self.current_quantity)

    def _check_result_not_negative(self, stock):
        self.ensure_one()
        result = stock + self.adjustment_quantity
        if float_compare(result, 0, precision_rounding=self.product_id.uom_id.rounding) < 0:
            raise UserError(
                _('%(product)s en %(location)s quedaría en %(result)s: hay %(stock)s y el ajuste es %(adjustment)s.')
                % {
                    'product': self.product_id.display_name,
                    'location': self.location_id.display_name,
                    'result': result,
                    'stock': stock,
                    'adjustment': self.adjustment_quantity,
                }
            )

    def _snapshot_quantity(self):
        self.ensure_one()
        self.theoretical_quantity = self.current_quantity
        self.counted_quantity = self.current_quantity + self.adjustment_quantity

    def _apply_adjustment(self):
        self.ensure_one()
        if self.applied:
            return

        # Se aplica el ajuste con signo sobre el stock de hoy. Hasta la 18.0.1.0.2 se
        # fijaba una cantidad contada absoluta, lo que revertía las ventas y entradas
        # hechas entre el envío y la aprobación (SAI2026100109, SAI2026090069).
        Quant = self.env['stock.quant']
        quants = self._get_quants()
        stock = sum(quants.mapped('quantity'))
        self._check_result_not_negative(stock)
        difference = self.adjustment_quantity
        self.write({
            'quantity_at_approval': stock,
            'applied_difference': difference,
        })

        if quants:
            quant = quants[0]
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

        quant = quant.with_context(**{
            'inventory_name': inventory_name,
            CLAVE_SOLICITUD_APROBADA: SOLICITUD_APROBADA,
        })
        quant.inventory_quantity = quant.quantity + difference
        quant._apply_inventory()

        domain = [
            ('id', '>', last_move_id),
            ('product_id', '=', self.product_id.id),
            ('is_inventory', '=', True),
            ('company_id', '=', quant.company_id.id),
            '|',
            ('location_id', '=', self.location_id.id),
            ('location_dest_id', '=', self.location_id.id),
        ]
        if self.lot_id:
            domain.append(('move_line_ids.lot_id', '=', self.lot_id.id))
        new_moves = self.env['stock.move'].search(domain)
        if new_moves:
            self.move_ids = [(6, 0, new_moves.ids)]

        self.applied = True
