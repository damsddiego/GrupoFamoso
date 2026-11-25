from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

# Datos del comprobante electrónico que una factura sustituta no hereda.
CAMPOS_FE_SIN_HEREDAR = (
    "number_electronic",
    "sequence",
    "date_issuance",
    "state_tributacion",
    "einvoice_had_rejection",
    "xml_comprobante",
    "fname_xml_comprobante",
    "xml_respuesta_tributacion",
    "fname_xml_respuesta_tributacion",
    "state_email",
    "electronic_invoice_return_message",
    "consecutive_number_receiver",
)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Add a computed field to track credit note totals
    credit_note_total = fields.Monetary(
        string='Total Credit Notes',
        compute='_compute_credit_note_total',
        store=True,
        help='Total amount of credit notes created for this invoice'
    )

    # La nota de crédito hecha desde la factura no mueve inventario: la
    # mercadería que regresa entra por Devoluciones (sng_return). Estos dos
    # campos guardan la recepción de las notas de crédito anteriores a ese
    # cambio y la que informa sng_return en las suyas.
    return_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación de devolución',
        domain="[('usage', '=', 'internal')]",
        copy=False,
        readonly=True,
        help='Ubicación a la que regresó la mercadería de esta nota de crédito.'
    )

    has_stock_delivery = fields.Boolean(
        string='Has Stock Delivery',
        compute='_compute_has_stock_delivery',
        store=False,
        help='Indicates if this invoice comes from a sale order with a completed delivery'
    )

    stock_return_picking_id = fields.Many2one(
        'stock.picking',
        string='Recepción de devolución',
        copy=False,
        readonly=True,
        # El control de anulaciones se recalcula cuando cambia el estado de
        # la recepción: sin índice, cada traslado recorrería account_move.
        index='btree_not_null',
        help='Recepción de la mercadería devuelta por esta nota de crédito.'
    )
    sng_estado_recepcion = fields.Selection(
        related='stock_return_picking_id.state',
        string='Estado de la recepción',
    )

    sng_motivo_anulacion_id = fields.Many2one(
        'sng.motivo.anulacion',
        string='Motivo de anulación',
        copy=False,
        tracking=True,
        ondelete='restrict',
        help='Obligatorio en las notas de crédito de cliente que anulan el '
             'documento de referencia (código 01).'
    )
    sng_factura_anulada_id = fields.Many2one(
        'account.move',
        string='Sustituye a la factura',
        copy=False,
        readonly=True,
        index='btree_not_null',
        check_company=True,
        help='Factura anulada que esta factura sustituye.'
    )
    sng_factura_sustituta_id = fields.Many2one(
        'account.move',
        string='Factura sustituta',
        copy=False,
        readonly=True,
        index='btree_not_null',
        check_company=True,
        help='Factura emitida en lugar de la que anuló esta nota de crédito.'
    )
    sng_estado_sustituta = fields.Selection(
        related='sng_factura_sustituta_id.state',
        string='Estado de la sustituta',
    )
    sng_puede_crear_sustituta = fields.Boolean(
        compute='_compute_sng_puede_crear_sustituta',
    )
    sng_puede_crear_nc = fields.Boolean(
        compute='_compute_sng_puede_crear_nc',
    )
    sng_estado_control = fields.Selection(
        [
            ('ok', 'En orden'),
            ('sin_refactura', 'Sin refactura'),
            ('recepcion_pendiente', 'Recepción pendiente'),
        ],
        string='Control de anulación',
        compute='_compute_sng_estado_control',
        store=True,
        help='Sin refactura: anulación total (código 01) con un motivo que '
             'requiere refactura y cuya factura sustituta no existe o no está '
             'confirmada. Recepción pendiente: nota de crédito anterior con '
             'una recepción que nadie validó ni canceló.'
    )

    @api.depends('reversed_entry_id', 'reversed_entry_id.invoice_line_ids.sale_line_ids.order_id.picking_ids')
    def _compute_has_stock_delivery(self):
        """Check if the invoice (or reversed invoice for credit notes) has a completed stock delivery"""
        for move in self:
            move.has_stock_delivery = False

            # For credit notes, check the original invoice
            invoice_to_check = move.reversed_entry_id if move.move_type == 'out_refund' else move

            if not invoice_to_check:
                continue

            # Get sale orders from invoice lines
            sale_orders = invoice_to_check.invoice_line_ids.mapped('sale_line_ids.order_id')

            if sale_orders:
                # Check if there are completed deliveries (outgoing pickings in done state)
                completed_deliveries = sale_orders.mapped('picking_ids').filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                )
                move.has_stock_delivery = bool(completed_deliveries)

    @api.depends('reversed_entry_id', 'reversed_entry_id.line_ids', 'state')
    def _compute_credit_note_total(self):
        """Compute the total amount of credit notes for an invoice"""
        for move in self:
            if move.move_type == 'out_refund' and move.reversed_entry_id:
                # Find all credit notes linked to the original invoice
                credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', move.reversed_entry_id.id),
                    ('state', 'not in', ['cancel', 'draft']),
                    ('move_type', '=', 'out_refund')
                ])
                move.credit_note_total = sum(credit_notes.mapped('amount_total'))
            else:
                move.credit_note_total = 0.0

    @api.model
    def _sng_puede_crear_nota_credito(self):
        return self.env.su or self.env.user.has_group(
            'cr_electronic_invoice_credit_limit.group_sng_crear_nota_credito'
        )

    @api.depends_context('uid')
    def _compute_sng_puede_crear_nc(self):
        self.sng_puede_crear_nc = self._sng_puede_crear_nota_credito()

    @api.model
    def _sng_check_puede_crear_nota_credito(self):
        """La regla de registro del grupo ya lo impide; aquí se explica."""
        if not self._sng_puede_crear_nota_credito():
            raise AccessError(_(
                "No tiene permiso para crear notas de crédito de cliente. "
                "Pídala a un usuario autorizado (grupo «Crear notas de crédito "
                "de cliente»)."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        default_type = self.env.context.get('default_move_type')
        if any(vals.get('move_type', default_type) == 'out_refund' for vals in vals_list):
            self._sng_check_puede_crear_nota_credito()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('move_type') == 'out_refund' and any(
            move.move_type != 'out_refund' for move in self
        ):
            self._sng_check_puede_crear_nota_credito()
        return super().write(vals)

    def _sng_es_anulacion_total(self):
        """NC de cliente código 01 por el monto completo de su factura."""
        self.ensure_one()
        original = self.reversed_entry_id
        return (
            self.move_type == 'out_refund'
            and self.reference_code_id.code == '01'
            and original.move_type == 'out_invoice'
            and not self.sng_return_id
            and float_compare(
                self.amount_total, original.amount_total,
                precision_rounding=self.currency_id.rounding or 0.01,
            ) == 0
        )

    @api.depends(
        'move_type', 'state', 'reference_code_id.code', 'sng_return_id',
        'amount_total', 'reversed_entry_id.amount_total',
        'sng_factura_sustituta_id.state',
    )
    def _compute_sng_puede_crear_sustituta(self):
        for move in self:
            move.sng_puede_crear_sustituta = (
                move.state == 'posted'
                and move._sng_es_anulacion_total()
                and move.sng_factura_sustituta_id.state in (False, 'cancel')
            )

    @api.depends(
        'move_type', 'state', 'reference_code_id.code', 'sng_return_id',
        'amount_total', 'reversed_entry_id.amount_total',
        'stock_return_picking_id.state', 'sng_factura_sustituta_id.state',
        'sng_motivo_anulacion_id.requiere_refactura',
    )
    def _compute_sng_estado_control(self):
        for move in self:
            if move.move_type != 'out_refund' or move.state != 'posted':
                move.sng_estado_control = False
                continue
            picking = move.stock_return_picking_id
            if not move.sng_return_id and picking and picking.state not in ('done', 'cancel'):
                move.sng_estado_control = 'recepcion_pendiente'
            elif (
                move._sng_es_anulacion_total()
                # Sin motivo (anulaciones anteriores al control) o con un
                # motivo que no lleva factura nueva no hay nada que esperar.
                and move.sng_motivo_anulacion_id.requiere_refactura
                and move.sng_factura_sustituta_id.state != 'posted'
            ):
                move.sng_estado_control = 'sin_refactura'
            else:
                move.sng_estado_control = 'ok'

    def _sng_reemplaza_nc_de_devolucion(self):
        """Reemplazo de una NC de Devoluciones rechazada por Hacienda."""
        self.ensure_one()
        return bool(
            'replaces_invoice_id' in self._fields
            and self.replaces_invoice_id.sng_return_id
        )

    def _sng_check_control_nota_credito(self):
        for move in self:
            if move.move_type != 'out_refund':
                continue
            if (
                move.reference_code_id.sng_politica_devolucion == 'devuelve'
                and not move.sng_return_id
                and not move._sng_reemplaza_nc_de_devolucion()
            ):
                raise UserError(_(
                    "La nota de crédito usa el código «%(code)s», que es por devolución de "
                    "mercadería.\n\n"
                    "Esas notas de crédito se generan desde Devoluciones, después de que "
                    "bodega recibe la mercadería. Si la mercadería no regresa, use otro "
                    "código de referencia."
                ) % {'code': move.reference_code_id.display_name})
            if move.reference_code_id.code == '01' and not move.sng_motivo_anulacion_id:
                raise UserError(_(
                    "Indique el motivo de anulación antes de confirmar la nota de crédito."
                ))

    def _post(self, soft=True):
        self._sng_check_control_nota_credito()
        return super()._post(soft=soft)

    def _sng_recepciones_anteriores(self):
        """Recepciones que la versión anterior creaba al confirmar la NC."""
        return self.filtered(
            lambda move: move.move_type == 'out_refund' and not move.sng_return_id
        ).stock_return_picking_id

    @api.model
    def _sng_recepcion_devuelta(self, picking):
        """La recepción validada ya salió completa otra vez (botón Devolver)."""
        for move in picking.move_ids.filtered(lambda m: m.state == 'done'):
            devuelto = sum(
                returned.product_uom._compute_quantity(returned.quantity, move.product_uom)
                for returned in move.returned_move_ids
                if returned.state == 'done'
            )
            if float_compare(
                devuelto, move.quantity, precision_rounding=move.product_uom.rounding,
            ) < 0:
                return False
        return True

    def _sng_check_recepciones_anteriores(self):
        validadas = self._sng_recepciones_anteriores().filtered(
            lambda picking: picking.state == 'done'
            and not self._sng_recepcion_devuelta(picking)
        )
        if validadas:
            raise UserError(_(
                "No puede anular la nota de crédito porque tiene una recepción validada "
                "(%(pickings)s): esa mercadería ya entró a bodega.\n\n"
                "Primero devuelva la recepción desde Inventario."
            ) % {'pickings': ', '.join(validadas.mapped('name'))})

    def _sng_cancelar_recepciones_anteriores(self):
        # Anular la nota de crédito anula su recepción pendiente; quien anula
        # no siempre tiene permisos de inventario.
        self._sng_recepciones_anteriores().sudo().filtered(
            lambda picking: picking.state not in ('done', 'cancel')
        ).action_cancel()

    def button_draft(self):
        self._sng_check_recepciones_anteriores()
        res = super().button_draft()
        self._sng_cancelar_recepciones_anteriores()
        return res

    def button_cancel(self):
        self._sng_check_recepciones_anteriores()
        res = super().button_cancel()
        self._sng_cancelar_recepciones_anteriores()
        return res

    def action_view_stock_return(self):
        """Open the stock return picking"""
        self.ensure_one()
        return {
            'name': _('Recepción de devolución'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.stock_return_picking_id.id,
            'target': 'current',
        }

    def _sng_action_ver_factura(self, move, name):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
            'context': {'default_move_type': move.move_type},
        }

    def action_sng_ver_factura_sustituta(self):
        self.ensure_one()
        return self._sng_action_ver_factura(self.sng_factura_sustituta_id, _('Factura sustituta'))

    def action_sng_ver_factura_anulada(self):
        self.ensure_one()
        return self._sng_action_ver_factura(self.sng_factura_anulada_id, _('Factura anulada'))

    def _sng_crear_factura_sustituta(self, default=None):
        """Factura en borrador que sustituye a la anulada por esta NC.

        Es la misma copia que hace «Revertir y crear factura» del asistente
        estándar: conserva el vínculo de cada línea con la orden de venta, de
        modo que la entrega original sigue siendo la de la factura nueva.
        """
        self.ensure_one()
        original = self.reversed_entry_id
        values = dict(default or {}, sng_factura_anulada_id=original.id)
        for fname in CAMPOS_FE_SIN_HEREDAR:
            if fname in self._fields:
                values[fname] = False
        data = original.with_context(include_business_fields=True).copy_data(values)[0]
        data['line_ids'] = [
            line for line in data['line_ids']
            if line[2]['display_type'] in ('product', 'line_section', 'line_note')
        ]
        sustituta = self.env['account.move'].create(data)
        self.sng_factura_sustituta_id = sustituta
        sustituta.message_post(body=_(
            "Factura creada para sustituir a %(invoice)s."
        ) % {'invoice': original.display_name})
        return sustituta

    def action_sng_crear_factura_sustituta(self):
        self.ensure_one()
        if self.sng_factura_sustituta_id.state in ('draft', 'posted'):
            raise UserError(_(
                "Esta nota de crédito ya tiene una factura sustituta: %(invoice)s."
            ) % {'invoice': self.sng_factura_sustituta_id.display_name})
        if not self.sng_puede_crear_sustituta:
            raise UserError(_(
                "Solo se crea una factura sustituta desde una nota de crédito "
                "confirmada que anula su factura por el monto completo (código 01)."
            ))
        sustituta = self._sng_crear_factura_sustituta()
        return self._sng_action_ver_factura(sustituta, _('Factura sustituta'))

    @api.constrains('move_type', 'reversed_entry_id', 'amount_total', 'state')
    def _check_credit_note_limit(self):
        """Ensure credit note total doesn't exceed original invoice amount"""
        for move in self:
            # Only check for out_refund (credit notes) that are linked to an original invoice
            # and are not in cancel state
            if (move.move_type == 'out_refund' and move.reversed_entry_id and 
                move.state not in ['cancel', 'draft']):
                original_invoice = move.reversed_entry_id
                # Skip the check if original invoice is cancelled
                if original_invoice.state == 'cancel':
                    continue
                    
                # Calculate total of all credit notes including this one
                # Exclude draft and cancelled credit notes
                existing_credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', original_invoice.id),
                    ('state', 'not in', ['cancel', 'draft']),
                    ('move_type', '=', 'out_refund'),
                    ('id', '!=', move.id)
                ])
                total_credit_amount = sum(existing_credit_notes.mapped('amount_total')) + move.amount_total
                
                # Allow a small tolerance for rounding differences
                if total_credit_amount > (original_invoice.amount_total + 0.01):
                    raise ValidationError(_(
                        "The total amount of credit notes (%.2f) cannot exceed "
                        "the original invoice amount (%.2f).\n"
                        "Original Invoice: %s\n"
                        "Current Credit Notes Total: %.2f\n"
                        "This Credit Note Amount: %.2f"
                    ) % (
                        total_credit_amount,
                        original_invoice.amount_total,
                        original_invoice.name,
                        sum(existing_credit_notes.mapped('amount_total')),
                        move.amount_total
                    ))