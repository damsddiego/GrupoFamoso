# SNG Análisis de Crédito con IA

Evalúa solicitudes de **apertura de crédito** combinando dos fuentes:

1. **Estudio de crédito en PDF** (buró tipo Cero Riesgo): la IA lee el
   documento completo — resultado de la evaluación, reglas no aprobadas,
   referencias con otros acreedores, juicios, patrimonio y gravámenes,
   consultas recientes al buró.
2. **Comportamiento interno en TODAS las compañías del grupo** (si el
   solicitante ya es cliente): ventas y antigüedad, saldo abierto y vencido,
   días de atraso **reales** (fecha de conciliación vs vencimiento), notas de
   crédito. El cruce es por partner y también por **cédula (vat)**, porque hay
   clientes duplicados entre compañías.

Menú: **Análisis de Crédito → Solicitudes**, visible solo para el grupo
"Análisis de crédito (IA)" (Ajustes → Usuarios → Permisos de acceso, sección
"SNG Análisis de Crédito"). Nadie lo implica; solo membresía explícita.

## Flujo

1. Crear la solicitud: cliente **nuevo** o **existente**, monto, plazo,
   compañía que otorgaría y el estudio PDF (obligatorio para cliente nuevo;
   recomendado para existente).
2. Botón **Analizar con IA** → recomendación estructurada:
   - **Aprobar / Aprobar condicionado / Rechazar**
   - Nivel de riesgo (bajo/medio/alto), **límite sugerido** en ₡ y plazo
     sugerido en días
   - Resumen ejecutivo, factores positivos, factores de riesgo y condiciones
     (garantías, fiador, límite escalonado, etc.)
3. La pestaña "Comportamiento en el grupo" muestra la tabla por compañía que
   se envió a la IA (transparencia del dato).
4. Decisión final humana: botones **Aprobar / Rechazar** (la IA solo
   recomienda). Todo queda trazado en el chatter.

Si alguien se registra como "cliente nuevo" pero su cédula ya tiene
movimientos en alguna compañía, el sistema lo detecta e incluye igual su
comportamiento, y la IA lo advierte.

## Configuración

- API key: reutiliza `sng_ruteros_pagos.anthropic_api_key` (respaldo:
  `sng_credito_ia.anthropic_api_key`). Modelo:
  `sng_credito_ia.anthropic_model` (default `claude-opus-4-8`).
- Costo aproximado: ~$0.10–0.20 por análisis con PDF (solo se consume al
  presionar el botón; no hay cron).

## Notas técnicas

- Modelo `sng.credito.solicitud` (chatter, secuencia CRED/AAAA/NNNN).
- El comportamiento se consulta en SQL directo sobre `account_move` y
  `account_partial_reconcile`; los días de atraso de facturas pagadas usan la
  fecha máxima de conciliación del apunte por cobrar.
- El PDF viaja a la API como bloque `document` base64; la respuesta se fuerza
  a JSON con `output_config` + json_schema.
- Anti-inyección: el prompt ordena nunca seguir instrucciones contenidas en
  el PDF o el JSON.
