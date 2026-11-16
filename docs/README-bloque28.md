# Bloque 28 — Latencia y costo del flujo RAG completo

## Objetivo

Cerrar la Unidad 2.5 instrumentando el RAG real (índice markdown + vectorial + expansión por sección, k=3) de extremo a extremo. Cada consulta registra el tiempo de cada etapa, los tokens reportados por Gemini, un costo estimado con tarifas oficiales y su procedencia, en un registro JSONL persistente. Además se añade un *preflight* que diagnostica el sistema sin llamar a Gemini.

## Arquitectura

| Archivo | Responsabilidad |
|---|---|
| `src/rag/medicion.py` | `Medidor`: context managers `etapa()` y `total()` con `time.perf_counter()`. Total medido de forma independiente; `sobrecarga_ms` = total − suma de etapas |
| `src/rag/costos.py` | `calcular_costo` (función pura), `costo_por_tokens`, `extraer_uso` (`usage_metadata`), tarifas con procedencia y `desglose_costo` (calculado / estimado / desconocido) |
| `src/rag/observabilidad.py` | `consultar_instrumentado`, `guardar_registro` / `leer_registros` (JSONL) y `estadisticas` |
| `src/rag/preflight.py` | Diagnóstico local (`python -m src.rag.preflight`) |
| `src/registro_rag.py` | CLI: consultas instrumentadas y `--comparar-ruta` |
| `src/leer_registros_rag.py` | CLI: estadísticas e informe `docs/resultados_bloque28.md` |
| `data/tarifas_gemini.json` | Tarifas en USD por millón de tokens, con fuente y fecha de consulta |
| `src/rag/recuperador.py` | **Solo se añadió** `buscar_por_vector_con_score`; no se modificó nada existente |

Se reutilizan sin cambios la carga del índice (`cargar_indice`), la expansión (`expandir_hasta_k`), el formato del contexto, el prompt, los reintentos (`llamar_con_reintentos` → `src/cliente.py`) y `texto_de_respuesta`, que admite contenido en bloques como en el Bloque 22.

## Etapas medidas

```text
total (medido de forma independiente)
├─ validacion_indice    pregunta y k válidos; colección no vacía (count local)
├─ embed_query          1 llamada de red a Gemini (gemini-embedding-001), con reintentos
├─ busqueda_vectorial   consulta HNSW local en Chroma con el vector ya calculado (20 candidatos)
├─ expansion_contexto   lecturas locales en Chroma para unir cada chunk con su sección (small-to-big)
├─ construccion_prompt  contexto numerado [n] + plantilla del prompt
└─ generacion           1 llamada de red a Gemini (AI_MODEL), con reintentos
sobrecarga_ms = total − Σ etapas
```

Fuera del total por consulta, y registrados aparte en `preparacion_ejecucion_ms`: la carga del índice y la creación del modelo.

**Sin doble embedding.** `similarity_search_with_score(pregunta)` de langchain-chroma 1.1.0 hace internamente `embed_query` y luego consulta por vector. La ruta instrumentada hace `embed_query` una vez y llama a `similarity_search_by_vector_with_relevance_scores(vector)`, la misma consulta interna. Se verificó con datos reales (3 preguntas: mismas unidades, distancias y texto de contexto, con 1 `embed_query` por ruta) y con pruebas offline. Los reintentos de red quedan **dentro** de la etapa en que ocurren.

## Latencia local frente a latencia de red

`embed_query` y `generacion` dependen de la red y del servicio de Google: su variación entre ejecuciones de la misma pregunta llegó a ~3,4× para el embedding y ~2,3× para la generación. Búsqueda, expansión y prompt son locales y tardan milisegundos. La primera consulta de cada proceso es más lenta (conexión y cachés frías), así que conviene separarla al analizar.

## Tokens

- **Generación:** se leen de `usage_metadata` de la respuesta de LangChain. Según langchain-google-genai 4.4.2: `input_tokens` = tokens del prompt (+ herramientas); `output_tokens` = candidatos + razonamiento; `total_tokens` = `total_token_count` de la API. Se registra `otros = total − entrada − salida`, sin suponer que sea 0, y el razonamiento aparte. Si no hay metadatos, todo queda en `null` con estado `no_disponible`.
- **Embedding de consulta:** la API de Gemini **no devuelve conteo** para `embed_content` (verificado con una llamada real: `metadata=None` y `statistics=None`). Se registra `tokens: null` con estado `no_reportado_por_el_proveedor`. Su costo aparece aparte como **estimación** (caracteres/4) y no se suma al total conocido.

## Costo

```text
costo = tokens_entrada × tarifa_entrada / 1 000 000 + tokens_salida × tarifa_salida / 1 000 000   (USD)
```

`calcular_costo` devuelve `None` si falta cualquier dato: un costo parcial no se presenta como total.

Tarifas aplicadas (`data/tarifas_gemini.json`), del nivel de pago y consultadas el 16/11/2026 en la página oficial de precios de la API de Gemini (`ai.google.dev/gemini-api/docs/pricing`, que redirige a `aistudio.google.com/docs/pricing`; la página no indica fecha de actualización):

| Modelo | Entrada (USD/M) | Salida (USD/M) |
|---|---|---|
| `gemini-3.5-flash-lite` | 0,30 | 2,50 (incluye razonamiento) |
| `gemini-embedding-001` | 0,15 | — |

| Tipo | Significado |
|---|---|
| Calculado | Tokens reales × tarifa verificada. Sigue siendo una **estimación** del cargo |
| Estimado | Tokens aproximados (embedding de consulta) |
| Facturado | **Desconocido.** En el nivel gratuito, la tarifa es «Free of charge», y esta clave mostró errores 429 de cuota *free tier* en bloques anteriores. Caché, descuentos y redondeos tampoco se reflejan |

## Registro JSONL

`registros_latencia_costo.jsonl` (UTF-8, una línea por consulta, solo se agrega y está excluido de Git). Cada registro guarda: `id_ejecucion`, `id_consulta`, `timestamp`, `tipo_medicion` (real/simulada), pregunta, modelos, índice/colección, modo, expansión, k, candidatos, `tiempos_ms`, `tiempo_total_ms`, `sobrecarga_ms`, etapas fallidas, recuperación (candidatos, unidades, secciones únicas, chunks, posiciones de origen, distancias), fuentes, caracteres de contexto y de prompt, tokens, costo desglosado, tarifas con fuente y fecha, longitud de la respuesta, citas usadas, intentos, estado y error.

No guarda claves ni el texto de la respuesta. Si una etapa falla, se guarda el registro con `estado: "error"`, los tiempos disponibles y la etapa fallida, y luego se vuelve a lanzar la excepción.

## Preflight

`python -m src.rag.preflight` comprueba, sin llamar a Gemini:

- **`.gitignore`:** que exista y excluya `.env`, `.venv/` y `vectorstore/` (y verifica con `git check-ignore`); también avisa de líneas que parecen comandos pegados por error y de registros generados que no estén excluidos.
- **Staging:** que no haya secretos ni archivos generados en el área de staging.
- **Índice:** que haya una clave configurada (sin validarla), que la colección exista con su número de chunks y documentos, que todos los chunks tengan `fuente` y que el modelo de embeddings coincida con la configuración.
- **Otros:** tarifas de los modelos configurados y el dataset del Bloque 27.

Distingue `ERROR` (sale con código 1) de `ADVERTENCIA` (sale con 0). **No** verifica la validez de la clave ni la cuota.

## Ejecución (PowerShell, desde la raíz con `.venv` activado)

```powershell
python -m src.rag.preflight
python -m src.registro_rag --comparar-ruta                       # 6 embed_query, sin generar
python -m src.registro_rag                                       # c01, c07, c04 con k=3
python -m src.registro_rag --casos c07-aprobacion --k 6
python -m src.leer_registros_rag --informe
python -m pytest tests/test_rag_latencia.py tests/test_rag_costos.py tests/test_rag_observabilidad.py -v
```

## Resultados

Ver [resultados_bloque28.md](resultados_bloque28.md) (generado desde el JSONL) y el análisis en [ensayo-bloque28.md](ensayo-bloque28.md).
