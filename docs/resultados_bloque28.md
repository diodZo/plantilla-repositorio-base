# Resultados del Bloque 28 — latencia, tokens y costo

> Generado por `python -m src.leer_registros_rag --informe` a partir de `registros_latencia_costo.jsonl`. Solo contiene datos **reales** registrados; no hay cifras ilustrativas. El análisis está en `docs/ensayo-bloque28.md`.

Registros leídos: 5 · consultas completas reales: 5 · consultas con error: 0 · líneas ilegibles: 0.

## Consultas registradas

| Ejecución | Caso | k | Estado | Total ms | Embed ms | Búsqueda ms | Expansión ms | Prompt ms | Generación ms | Sobrecarga ms | Tokens entrada | Tokens salida (razonamiento) | Total tokens | Secciones | Car. contexto | Costo gen. USD | Fuentes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261116T231029Z-60069 | c01-backoff | 3 | ok | 5813.7 | 427.0 | 11.1 | 7.1 | 10.9 | 5317.5 | 0.1 | 735 | 26 | 761 | 3 | 1621 | 0.00028550 | README.md, docs/README-bloque20.md, docs/ensayo-bloque13.md |
| 20261116T231029Z-60069 | c07-aprobacion | 3 | ok | 1136.2 | 364.9 | 3.5 | 5.1 | 0.3 | 761.4 | 0.1 | 929 | 92 | 1021 | 3 | 2567 | 0.00050870 | docs/README-bloque23.md, docs/limites_autonomia_agente.md |
| 20261116T231029Z-60069 | c04-tarifa | 3 | ok | 2314.3 | 1239.4 | 9.7 | 7.5 | 0.3 | 1056.5 | 0.1 | 958 | 123 | 1081 | 2 | 2101 | 0.00059490 | docs/decision-arquitectura.md, docs/ensayo-bloque13.md |
| 20261116T231048Z-69728 | c07-aprobacion | 6 | ok | 1415.8 | 406.2 | 4.0 | 10.3 | 7.9 | 945.6 | 0.1 | 1299 | 92 | 1391 | 6 | 4073 | 0.00061970 | docs/README-bloque23.md, docs/limites_autonomia_agente.md |
| 20261116T231054Z-f6049 | c07-aprobacion | 3 | ok | 3058.2 | 1250.8 | 5.7 | 6.1 | 7.7 | 1748.6 | 0.1 | 929 | 83 | 1012 | 3 | 2567 | 0.00048620 | docs/README-bloque23.md, docs/limites_autonomia_agente.md |

## Estadísticas (consultas reales completas)

Con n = 5, estas cifras describen solo estas ejecuciones; **no** representan el rendimiento habitual.

| Medida | n | Media | Mediana | Mínimo | Máximo |
|---|---|---|---|---|---|
| Total (ms) | 5 | 2747.66 | 2314.32 | 1136.20 | 5813.73 |
| Sobrecarga fuera de etapas (ms) | 5 | 0.08 | 0.08 | 0.06 | 0.10 |
| Etapa validacion_indice (ms) | 5 | 24.53 | 39.26 | 0.77 | 41.69 |
| Etapa embed_query (ms) | 5 | 737.69 | 427.04 | 364.94 | 1250.82 |
| Etapa busqueda_vectorial (ms) | 5 | 6.80 | 5.74 | 3.48 | 11.12 |
| Etapa expansion_contexto (ms) | 5 | 7.21 | 7.10 | 5.06 | 10.28 |
| Etapa construccion_prompt (ms) | 5 | 5.43 | 7.66 | 0.30 | 10.91 |
| Etapa generacion (ms) | 5 | 1965.92 | 1056.51 | 761.36 | 5317.53 |
| Tokens de entrada | 5 | 970.00 | 929 | 735 | 1299 |
| Tokens de salida | 5 | 83.20 | 92 | 26 | 123 |
| Tokens de razonamiento (incluidos en salida) | 0 | — | — | — | — |
| Caracteres de prompt por token de entrada | 5 | 3.99 | 4.13 | 3.54 | 4.15 |
| Costo de generación (USD, estimado a tarifa de pago) | 5 | 0.00049900 | 0.00050870 | 0.00028550 | 0.00061970 |

Tarifas aplicadas (verificada, consultadas 2026-11-16): generación {'entrada': 0.3, 'salida': 2.5}, embedding {'entrada': 0.15} USD por millón de tokens. Fuente: https://ai.google.dev/gemini-api/docs/pricing (redirige a https://aistudio.google.com/docs/pricing). Son costos estimados a partir de tokens; no son importes facturados.
