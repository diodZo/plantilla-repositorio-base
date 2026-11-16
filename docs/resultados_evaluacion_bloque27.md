# Resultados de evaluación — Bloque 27

> Archivo generado por `python -m src.evaluar_bloque27` a partir de `docs/resultados_evaluacion_bloque27.json`, que conserva **todas** las ejecuciones. El análisis está en `docs/README-bloque27.md` y `docs/ensayo-bloque27.md`.

## Historial de ejecuciones

| Ejecución (UTC) | Dataset (huella) | Configuraciones | embed_query | embed_documents | Generaciones |
|---|---|---|---|---|---|
| 2026-11-16T22:53:33+00:00 | 9e7782ea8474 | indice_original, markdown, markdown_expandido, markdown_hibrido, markdown_hibrido_expandido | 26 | 0 | 2 |
| 2026-11-16T22:53:56+00:00 | 9e7782ea8474 | indice_original, markdown, markdown_expandido, markdown_hibrido, markdown_hibrido_expandido | 24 | 0 | 0 |

**Estabilidad (últimas dos ejecuciones):** rankings y promedios idénticos — 0 rankings distintos, 0 promedios distintos.

## Última ejecución: 2026-11-16T22:53:56+00:00

- Dataset: `data/evaluacion/bloque27_casos.json` (congelado 2026-11-16T22:51:22+00:00, huella `9e7782ea8474`): 12 casos, 10 con respuesta, 2 sin respuesta.
- Parámetros: k = [3, 5], candidatos = 20, máx. sección = 1200 caracteres.

### Índices (leídos de Chroma)

| Índice | Colección | Modelo de embeddings | Estrategia | chunk_size/overlap | Documentos | Chunks | Secciones |
|---|---|---|---|---|---|---|---|
| base | `corpus_proyecto_bloque24` | `models/gemini-embedding-001` | recursivo | 200/30 | 8 | 296 | — |
| markdown | `corpus_proyecto_bloque24_md` | `models/gemini-embedding-001` | markdown | 200/30 | 8 | 261 | 57 |

### Promedios (solo casos con respuesta)

| Configuración | Nivel | k | Precision | Recall | F1 | Hit | Caracteres de contexto | Chunks en contexto | Excluidos (sin respuesta) |
|---|---|---|---|---|---|---|---|---|---|
| indice_original | chunk | 3 | 0.367 | 0.800 | 0.490 | 0.800 | 419 | 3.0 | 2 |
| indice_original | chunk | 5 | 0.240 | 0.850 | 0.367 | 0.900 | 732 | 5.0 | 2 |
| markdown | chunk | 3 | 0.333 | 0.750 | 0.450 | 0.800 | 734 | 3.0 | 2 |
| markdown | chunk | 5 | 0.260 | 0.900 | 0.395 | 0.900 | 1210 | 5.0 | 2 |
| markdown_expandido | seccion | 3 | 0.417 | 0.950 | 0.560 | 1.000 | 2115 | 13.7 | 2 |
| markdown_expandido | seccion | 5 | 0.300 | 1.000 | 0.444 | 1.000 | 3429 | 22.2 | 2 |
| markdown_hibrido | chunk | 3 | 0.300 | 0.650 | 0.400 | 0.700 | 714 | 3.0 | 2 |
| markdown_hibrido | chunk | 5 | 0.200 | 0.700 | 0.305 | 0.700 | 1164 | 5.0 | 2 |
| markdown_hibrido_expandido | seccion | 3 | 0.350 | 0.800 | 0.470 | 0.900 | 2148 | 14.3 | 2 |
| markdown_hibrido_expandido | seccion | 5 | 0.287 | 1.000 | 0.428 | 1.000 | 3575 | 23.5 | 2 |

### Métricas por caso (Precision / Recall / F1 / Hit)

| Caso | indice_original k=3 | indice_original k=5 | markdown k=3 | markdown k=5 | markdown_expandido k=3 | markdown_expandido k=5 | markdown_hibrido k=3 | markdown_hibrido k=5 | markdown_hibrido_expandido k=3 | markdown_hibrido_expandido k=5 |
|---|---|---|---|---|---|---|---|---|---|---|
| c01-backoff | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c02-clave-filtrada | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c03-401-sin-respuesta | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — |
| c04-tarifa | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.333 / 0.500 / 0.400 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.500 / 0.500 / 0.500 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.333 / 0.500 / 0.400 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.500 / 0.500 / 0.500 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 |
| c05-herramientas | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c06-memoria | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c07-aprobacion | 0.000 / 0.000 / 0.000 / 0.000 | 0.200 / 0.500 / 0.286 / 1.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 / 0.000 | 0.333 / 0.500 / 0.400 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 |
| c08-trazas | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 |
| c09-indexacion | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.667 / 1.000 / 0.800 / 1.000 | 0.400 / 1.000 / 0.571 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c10-puntaje | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c11-fallback | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 | 0.333 / 1.000 / 0.500 / 1.000 | 0.200 / 1.000 / 0.333 / 1.000 |
| c12-bd-pedidos | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — | 0.000 / — / — / — |

### Peores casos (menor recall y luego menor F1)

- **indice_original, k=3:** c05-herramientas (R=0.000, F1=0.000); c07-aprobacion (R=0.000, F1=0.000); c01-backoff (R=1.000, F1=0.500)
- **indice_original, k=5:** c05-herramientas (R=0.000, F1=0.000); c07-aprobacion (R=0.500, F1=0.286); c01-backoff (R=1.000, F1=0.333)
- **markdown, k=3:** c05-herramientas (R=0.000, F1=0.000); c07-aprobacion (R=0.000, F1=0.000); c04-tarifa (R=0.500, F1=0.400)
- **markdown, k=5:** c05-herramientas (R=0.000, F1=0.000); c01-backoff (R=1.000, F1=0.333); c02-clave-filtrada (R=1.000, F1=0.333)
- **markdown_expandido, k=3:** c04-tarifa (R=0.500, F1=0.500); c01-backoff (R=1.000, F1=0.500); c02-clave-filtrada (R=1.000, F1=0.500)
- **markdown_expandido, k=5:** c01-backoff (R=1.000, F1=0.333); c02-clave-filtrada (R=1.000, F1=0.333); c05-herramientas (R=1.000, F1=0.333)
- **markdown_hibrido, k=3:** c05-herramientas (R=0.000, F1=0.000); c06-memoria (R=0.000, F1=0.000); c07-aprobacion (R=0.000, F1=0.000)
- **markdown_hibrido, k=5:** c05-herramientas (R=0.000, F1=0.000); c06-memoria (R=0.000, F1=0.000); c07-aprobacion (R=0.000, F1=0.000)
- **markdown_hibrido_expandido, k=3:** c06-memoria (R=0.000, F1=0.000); c07-aprobacion (R=0.500, F1=0.400); c04-tarifa (R=0.500, F1=0.500)
- **markdown_hibrido_expandido, k=5:** c01-backoff (R=1.000, F1=0.333); c02-clave-filtrada (R=1.000, F1=0.333); c05-herramientas (R=1.000, F1=0.333)

### Casos sin respuesta (se excluyen del recall)

| Caso | Distancia top‑1 (base) | Distancia top‑1 (markdown) | Abstención del generador |
|---|---|---|---|
| c03-401-sin-respuesta | 0.2567 | 0.2990 | sí (medida 2026-11-16T22:53:33+00:00): «La documentación proporcionada no contiene información suficiente para responder.» |
| c12-bd-pedidos | 0.3322 | 0.3533 | sí (medida 2026-11-16T22:53:33+00:00): «La documentación proporcionada no contiene información suficiente para responder [1][2][3].» |

Distancia top‑1 de los casos con respuesta: base 0.1773–0.2869; markdown 0.2269–0.2979.

### Limitaciones

- Dataset pequeño (10 casos con respuesta y 2 sin respuesta): un caso equivale a 0,1 en Recall/Hit promedio.
- Etiquetado hecho por el desarrollador del sistema, no por evaluadores externos independientes.
- Mide la recuperación, no la calidad de la respuesta generada.
- Las métricas de sección (nivel B) no son comparables uno a uno con las de chunk (nivel A): las unidades son más grandes.
- Sin umbral de distancia: los casos sin respuesta siempre reciben contexto; la abstención depende del modelo generativo.
