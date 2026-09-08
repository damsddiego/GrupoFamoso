# SNG Conciliación Bancaria con IA

Lee el estado de cuenta del banco (formato **BAC** en xlsx), lo importa al
extracto bancario **nativo** de Odoo y deja cada línea "montada": cliente
identificado y pago o factura sugeridos, para confirmar en el widget de
conciliación de Contabilidad (Enterprise). **Nada se concilia solo**: la
decisión siempre es de la persona.

## Flujo (Evelin)

1. **Conciliación IA → Importar estado de cuenta BAC**: subir el xlsx que
   genera el BAC ("Detalle de movimientos"). El diario se detecta solo por el
   número de cuenta; reimportar el mismo archivo no duplica líneas.
   **Las sugerencias se calculan solas al importar**: al instante las
   directas (pagos con monto exacto, cédula TEF, teléfono SINPE, facturas
   con saldo exacto) y en unos minutos las ambiguas (cola de IA en segundo
   plano). Un cron horario de barrido cubre las líneas que entren por otra
   vía (a mano u otro importador).
2. Conciliar por cualquiera de las dos puertas:
   - **Contabilidad → Conciliación (widget nativo)**: cada línea abre con
     el cliente y la contrapartida sugerida ya montados (si el motor nativo
     no encontró nada por su cuenta); la tarjeta muestra el badge de la
     sugerencia y hay filtros "Sugerido: …" / "IA en cola". Revisar y
     Validar; nunca se auto-concilia.
   - **Conciliación IA → Líneas del extracto**: trabajo en lote con las
     columnas Sugerencia/Confianza/Motivo y el botón "2 · Conciliar lo
     sugerido". El botón "1 · Sugerir con IA" queda para recalcular a
     demanda.
3. Significado de la columna Sugerencia:
   - **Pago registrado**: la línea corresponde a un pago ya capturado (p. ej.
     de la app de ruteros) — al conciliar, el pago pasa a "Pagado".
   - **Factura abierta**: no hay pago registrado; se sugieren las facturas.
   - **Revisar**: cliente identificado pero sin cruce exacto (el widget
     nativo propone sus documentos, porque la línea ya lleva el cliente).
   - **Sin coincidencia**: sin pistas — trabajo manual.
4. Confirmar: **Conciliar según sugerencia** en lote (usa el motor real del
   widget; reversible con "Deshacer" en el widget) o Validar una a una en el
   widget nativo, que ya abre montado.

## Reglas y límites importantes

- Solo cruza contra pagos **desde julio 2026** (parámetro
  `sng_conciliacion_bancaria.fecha_inicio`): antes de esa fecha los pagos se
  registraban directo contra la cuenta del banco (sin transitoria) y no hay
  nada que conciliar contra ellos.
- El export del BAC **no siempre lista todos los movimientos** (planillas y
  pagos masivos aparecen solo en el "Cuadro de Resumen"): el importador lo
  detecta y avisa cuánto falta (esos movimientos se registran a mano).
- Formatos BN y BCR: pendientes (se necesita un archivo de muestra de cada
  banco).
- Permiso: grupo **"Conciliación bancaria (IA)"** (más los permisos normales
  de contabilidad para el widget).

## IA

- Solo para líneas ambiguas, en lotes de 20, en segundo plano (cron
  `SNG Conciliación: cola de sugerencias IA`, disparado por el importador,
  el botón o el cron de barrido `SNG Conciliación: sugerencias automáticas
  (barrido)`, que corre cada hora sobre líneas sin sugerencia).
- Nunca inventa: solo elige entre candidatos reales (pagos con monto exacto,
  clientes parecidos por nombre, sus facturas abiertas) y valida el servidor.
- Key: `sng_ruteros_pagos.anthropic_api_key` (respaldo propio); modelo
  `claude-opus-4-8`. Costo estimado: ~$2–3 por estado de cuenta mensual
  completo; $0 si solo se usan las sugerencias instantáneas.

## Notas técnicas

- Importador: `sng.conciliacion.importar` (wizard). Valida saldos del archivo
  y compara contra su Cuadro de Resumen. `unique_import_id =
  BAC-{referencia}-{fecha}-{monto}` para el dedup.
- Matching: campos `sng_*` sobre `account.bank.statement.line`; los cruces de
  partner van por SQL directo porque `res.partner.company_id` es computado
  sin store en este prod (base_multi_company) y revienta las búsquedas ORM
  que lo ordenan/filtran.
- Conciliar usa `bank.rec.widget` (`.new({}) → _action_add_new_amls →
  _action_validate`), el mismo motor del widget Enterprise.
- Integración con el widget nativo: override de
  `bank.rec.widget._action_trigger_matching_rules` — si el motor nativo no
  montó nada, monta las amls de la sugerencia (`_sng_amls_sugeridas`,
  revalidadas al abrir). Nunca marca `matching_rules_allow_auto_reconcile`,
  así que el cron de auto-conciliación nativo jamás valida una sugerencia
  SNG. Badge y filtros heredan las vistas Enterprise del widget
  (`views/sng_bank_rec_widget_views.xml`): si un upgrade las mueve, el
  error es ruidoso y aislado en ese archivo.
- Arreglos hechos en este trabajo fuera del módulo (requieren el restart):
  - `cr_electronic_invoice/models/account_move.py` (~línea 3025): en lote,
    `super().action_post()` publicaba TODO el recordset dentro del loop →
    ahora publica solo el registro (igual que las otras ramas).
  - Parche core `account/models/account_move.py`
    (`_sng_xmlrpc_partner_replacement`): ordenaba por
    `res.partner.company_id` (no almacenado) → ahora ordena en Python.
  - Cuenta suspense 0.1112 (id 101): era tipo "fuera de balance" (bloqueaba
    crear líneas de extracto) → asset_current (commit directo, tenía 0
    movimientos).
