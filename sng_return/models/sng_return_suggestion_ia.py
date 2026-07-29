"""Capa de IA sobre la sugerencia de factura de origen.

La heuristica de ``sng_return_suggestion.py`` resuelve la mayoria de los casos.
La IA entra solo donde esa heuristica no decide: empate entre facturas elegibles
o confianza baja/media, y sobre todo cuando hay texto libre (notas de la
devolucion, motivo, comentarios del cliente) que ningun puntaje puede leer.

Reglas de seguridad del diseno:

* La IA elige **unicamente** entre las facturas candidatas elegibles que se le
  pasan; cualquier id fuera de esa lista se descarta.
* Una sugerencia de IA nunca se asigna sola. El campo ``invoice_id`` lo fija el
  Gerente de Devoluciones, porque la factura elegida determina la referencia del
  XML de la nota de credito ante Hacienda.
* Si la IA falla (sin llave, sin libreria, error de red) se conserva la
  sugerencia heuristica y se registra el motivo.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:  # pragma: no cover - entorno sin la libreria
    anthropic = None

KEY_SIN_CONFIGURAR = "PENDIENTE"

IA_SYSTEM_PROMPT = """Eres un asistente contable de una distribuidora en Costa Rica.

Recibes una linea de devolucion de un cliente y la lista cerrada de facturas
candidatas contra las que se podria acreditar. Tu tarea es elegir cual factura
es la de origen del producto devuelto.

Reglas:
- Solo puedes responder con un factura_id que este en la lista de candidatas.
- Si ninguna candidata es claramente la correcta, responde factura_id nulo.
- Da mas peso a: el lote o serie rastreado, la mencion explicita del numero de
  factura o de la orden en las notas, la coincidencia exacta de cantidad y
  precio, y la cercania de la fecha dentro de la ventana de devolucion.
- Las notas pueden estar mal escritas o ser aproximadas ("como en marzo",
  "el pedido de las cajas grandes"); usalas, pero no inventes datos.
- El puntaje heuristico que acompana a cada candidata es una referencia, no una
  orden: puedes contradecirlo si el texto libre lo justifica, y en ese caso
  explica por que.
- El motivo debe ser una sola frase en espanol, concreta y verificable con los
  datos que recibiste.
"""

IA_SCHEMA = {
    "type": "object",
    "properties": {
        "factura_id": {
            "type": ["integer", "null"],
            "description": "Id de la factura elegida, o null si ninguna aplica.",
        },
        "confianza": {
            "type": "string",
            "enum": ["alta", "media", "baja"],
        },
        "motivo": {
            "type": "string",
            "description": "Una frase en espanol explicando la eleccion.",
        },
    },
    "required": ["factura_id", "confianza", "motivo"],
    "additionalProperties": False,
}

CONFIANZA_IA_A_CAMPO = {
    "alta": "high",
    "media": "medium",
    "baja": "low",
}


class SngReturnLine(models.Model):
    _inherit = "sng.return.line"

    # ------------------------------------------------------------------
    # Configuracion
    # ------------------------------------------------------------------
    @api.model
    def _ia_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = (
            icp.get_param("sng_return.anthropic_api_key")
            or icp.get_param("sng_ruteros_pagos.anthropic_api_key")
            or ""
        ).strip()
        return {
            "enabled": icp.get_param("sng_return.ia_enabled", "").strip().lower()
            in ("1", "true", "t", "yes", "si", "sí"),
            "api_key": api_key,
            "model": (icp.get_param("sng_return.anthropic_model") or "claude-opus-5").strip(),
            "effort": (icp.get_param("sng_return.anthropic_effort") or "medium").strip(),
        }

    @api.model
    def _ia_disponible(self):
        params = self._ia_params()
        return bool(
            params["enabled"]
            and anthropic is not None
            and params["api_key"]
            and params["api_key"] != KEY_SIN_CONFIGURAR
        )

    def _ia_get_client(self):
        params = self._ia_params()
        if anthropic is None:
            raise UserError(_('Falta la libreria Python "anthropic" en el entorno.'))
        if not params["api_key"] or params["api_key"] == KEY_SIN_CONFIGURAR:
            raise UserError(_(
                "Configure sng_return.anthropic_api_key en Parametros del sistema."
            ))
        client = anthropic.Anthropic(api_key=params["api_key"], timeout=120.0, max_retries=1)
        return client, params

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------
    def _ia_build_payload(self, eligible):
        """Datos de la linea y de las candidatas elegibles, sin texto libre del sistema."""
        self.ensure_one()
        candidatas = []
        for item in eligible:
            invoice = item["invoice"]
            inv_lines = invoice.invoice_line_ids.filtered(
                lambda il: il.product_id == self.product_id and il.display_type == "product"
            )
            orders = inv_lines.sale_line_ids.order_id
            candidatas.append({
                "factura_id": invoice.id,
                "numero": invoice.name,
                "referencia": invoice.ref or "",
                "fecha": str(invoice.invoice_date or invoice.date or ""),
                "dias_transcurridos": item["days"],
                "cantidad_facturada": round(item["invoiced"], 3),
                "cantidad_disponible": round(item["available"], 3),
                "precio_unitario": round(
                    inv_lines[:1].price_unit if inv_lines else 0.0, 2
                ),
                "total_factura": round(invoice.amount_total, 2),
                "estado_pago": invoice.payment_state or "",
                "ordenes_venta": orders.mapped("name"),
                "vendedor": orders[:1].user_id.display_name if orders else "",
                "almacen": orders[:1].warehouse_id.display_name if orders else "",
                "puntaje_heuristico": item["score"],
                "motivos_heuristica": item["reasons"],
            })
        return {
            "devolucion": {
                "numero": self.return_id.name,
                "fecha": str(self.return_id.date_request or ""),
                "cliente": self.partner_id.display_name,
                "motivo": self.return_id.reason_id.display_name,
                "notas_devolucion": (self.return_id.notes or "")[:1500],
                "responsable": self.return_id.user_id.display_name,
                "almacen_recepcion": self.return_id.warehouse_id.display_name or "",
            },
            "linea": {
                "producto": self.product_id.display_name,
                "codigo_producto": self.product_id.default_code or "",
                "cantidad_a_devolver": round(self.quantity, 3),
                "unidad": self.uom_id.display_name,
                "notas_linea": (self.notes or "")[:1000],
            },
            "candidatas": candidatas,
        }

    # ------------------------------------------------------------------
    # Llamada
    # ------------------------------------------------------------------
    def _ia_consultar(self, results):
        """Pide a Claude que elija entre las candidatas elegibles.

        Devuelve un dict con ``invoice`` (recordset), ``confidence`` y ``reason``,
        o None si la IA no eligio ninguna.
        """
        self.ensure_one()
        eligible = [item for item in results if item["eligible"]]
        if not eligible:
            return None

        client, params = self._ia_get_client()
        ids_validos = {item["invoice"].id for item in eligible}
        payload = self._ia_build_payload(eligible)

        response = client.messages.create(
            model=params["model"],
            # Holgura: en Opus 5 el razonamiento viene activo por defecto y
            # comparte el tope con el texto de la respuesta.
            max_tokens=16000,
            system=IA_SYSTEM_PROMPT,
            output_config={
                "effort": params["effort"],
                "format": {"type": "json_schema", "schema": IA_SCHEMA},
            },
            messages=[{
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            }],
        )
        if response.stop_reason == "refusal":
            raise UserError(_("La IA rechazo la consulta de esta devolucion."))
        texto = next((b.text for b in response.content if b.type == "text"), None)
        if not texto:
            raise UserError(_("La IA no devolvio una respuesta utilizable."))

        data = json.loads(texto)
        factura_id = data.get("factura_id")
        # Blindaje: la IA solo puede elegir dentro de la lista cerrada.
        if factura_id not in ids_validos:
            return None
        elegida = next(item for item in eligible if item["invoice"].id == factura_id)
        return dict(
            elegida,
            confidence=CONFIANZA_IA_A_CAMPO.get(data.get("confianza"), "low"),
            reason=(data.get("motivo") or "").strip(),
        )

    # ------------------------------------------------------------------
    # Integracion con la heuristica
    # ------------------------------------------------------------------
    def _ia_debe_consultar(self, results, confidence):
        """La IA solo se invoca donde la heuristica no resuelve.

        Asi el costo se paga unicamente en los casos ambiguos: sin confianza
        alta y con al menos dos facturas elegibles compitiendo.
        """
        self.ensure_one()
        if not self._ia_disponible():
            return False
        if confidence == "high":
            return False
        return len([item for item in results if item["eligible"]]) >= 2

    def _apply_suggestion(self, results=None, source="heuristic"):
        """Aplica la heuristica y, si el caso es ambiguo, la refina con IA."""
        self.ensure_one()
        if results is None:
            results = self._score_invoice_candidates()
        best = super()._apply_suggestion(results=results, source=source)
        if not best or source == "ai":
            return best
        if not self._ia_debe_consultar(results, best["confidence"]):
            return best

        try:
            elegida = self._ia_consultar(results)
        except Exception as exc:  # noqa: BLE001 - la IA nunca tumba el flujo
            _logger.exception("SNG Return: fallo la sugerencia por IA")
            self.write({
                "suggestion_reason": "%s\n\n%s" % (
                    self.suggestion_reason or "",
                    _("La consulta a la IA fallo: %s") % str(exc)[:200],
                ),
            })
            return best

        if not elegida:
            return best

        motivos = [_("Elegida por IA: %s") % elegida["reason"]] if elegida["reason"] else []
        motivos += elegida["reasons"]
        self.write({
            "suggested_invoice_id": elegida["invoice"].id,
            "suggestion_score": elegida["score"],
            # La IA nunca marca confianza alta: su sugerencia siempre la
            # confirma el Gerente de Devoluciones antes de la nota de credito.
            "suggestion_confidence": (
                "medium" if elegida["confidence"] == "high" else elegida["confidence"]
            ),
            "suggestion_reason": "\n".join("• %s" % motivo for motivo in motivos),
            "suggestion_source": "ai",
            "suggestion_date": fields.Datetime.now(),
        })
        return dict(
            elegida,
            confidence=self.suggestion_confidence,
            margin=0.0,
        )

    def action_suggest_invoice_ia(self):
        """Fuerza la consulta a la IA aunque la heuristica ya haya decidido."""
        self.ensure_one()
        if not self._ia_disponible():
            raise UserError(_(
                "La sugerencia por IA no esta habilitada. Configure "
                "sng_return.ia_enabled y sng_return.anthropic_api_key en "
                "Parametros del sistema."
            ))
        results = self._score_invoice_candidates()
        if not [item for item in results if item["eligible"]]:
            raise UserError(_(
                "No hay facturas candidatas con disponible suficiente para consultar."
            ))
        elegida = self._ia_consultar(results)
        if not elegida:
            raise UserError(_(
                "La IA no encontro una factura clara entre las candidatas."
            ))
        motivos = [_("Elegida por IA: %s") % elegida["reason"]] if elegida["reason"] else []
        motivos += elegida["reasons"]
        self.write({
            "suggested_invoice_id": elegida["invoice"].id,
            "suggestion_score": elegida["score"],
            "suggestion_confidence": (
                "medium" if elegida["confidence"] == "high" else elegida["confidence"]
            ),
            "suggestion_reason": "\n".join("• %s" % motivo for motivo in motivos),
            "suggestion_source": "ai",
            "suggestion_date": fields.Datetime.now(),
        })
        return True
