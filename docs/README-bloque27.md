# Bloque 27 — Evaluación de la recuperación: precisión y exhaustividad

## Objetivo

Pasar de la evaluación visual del RAG (Bloques 24–26) a una evaluación **cuantitativa, reproducible y verificable**: Precision@k, Recall@k, F1 y Hit@k sobre un dataset etiquetado y congelado, ejecutada contra los índices Chroma reales sin reindexar.

## Componentes

| Archivo | Función |
|---|---|
| `src/rag/metricas.py` | Funciones puras: `precision_at_k`, `recall_at_k`, `f1_score`, `hit_at_k`, `metricas_en_k`, `promedio` |
| `src/rag/etiquetado.py` | Relevancia derivada de pasajes literales; identificadores de sección |
| `src/rag/evaluacion_bloque27.py` | Validación y congelado del dataset, evaluación por niveles, agregados, historial y estabilidad |
| `src/evaluar_bloque27.py` | CLI: `--etiquetar`, evaluación real, `--incluir-hibrido`, `--abstencion`, `--solo-informe` |
| `data/evaluacion/bloque27_casos.json` | 12 casos (10 con respuesta y 2 sin respuesta), congelado con huella SHA‑256 |
| `docs/resultados_evaluacion_bloque27.json` | Historial de **todas** las ejecuciones (se agrega, nunca se sobrescribe) |
| `docs/resultados_evaluacion_bloque27.md` | Informe generado desde el historial |
| `tests/test_rag_metricas_bloque27.py` | 33 pruebas offline (sin Gemini y sin Chroma) |

Se reutiliza la arquitectura existente: `buscar_con_score`, `fusionar_rrf`, `IndiceBM25`, `formatear_contexto` y la expansión del Bloque 26. El único cambio en código anterior fue extraer el bucle de expansión de `generador.recuperar` a `expansion.expandir_hasta_k`, sin cambiar su comportamiento (las 207 pruebas previas siguen pasando). Así, la evaluación mide **exactamente** las unidades que recibe el generador.

## Métricas

Sea *R* la lista de los primeros k IDs recuperados (sin duplicados, en orden) y *G* el conjunto de IDs relevantes.

- **Precision@k** = |R ∩ G| / |R|. ¿Qué proporción de lo entregado es útil? Si no se recupera nada, vale 0,0. Si el sistema devuelve menos de k elementos únicos, el denominador es lo devuelto.
- **Recall@k** = |R ∩ G| / |G|. ¿Qué proporción de lo relevante se encontró? Vale `None` si *G* está vacío (consulta sin respuesta): **no** se cuenta como 1,0 ni como 0,0.
- **F1** = 2PR / (P + R). Es la media armónica, que penaliza el desequilibrio entre ambas. Vale 0,0 si P = R = 0 y `None` si falta R.
- **Hit@k** = 1 si |R ∩ G| ≥ 1. Responde a «¿llegó algo útil?», pero no informa cuánto ruido acompaña al acierto ni si faltan otros relevantes.

**Hit@k frente a Precision@k:** con un solo chunk relevante, encontrarlo en la posición 1 de k=5 da Hit = 1,0, pero Precision = 0,2. Hit mide si el sistema sirve como mínimo; Precision mide cuánto ruido se envía al generador.

**Techo estructural de la precisión:** la mayoría de los casos tiene 1 o 2 chunks relevantes. Con este dataset, la Precision@3 máxima alcanzable a nivel de chunk es 0,500 y la Precision@5, 0,300. Una precisión «baja» en términos absolutos puede estar cerca de ese máximo.

Ejemplo del curso (`["doc2", "doc0", "doc4"]`, relevante `{"doc0"}`), verificado en las pruebas:

| k | Precision | Recall | F1 | Hit |
|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 |
| 2 | 0,5 | 1 | 0,667 | 1 |
| 3 | 0,333 | 1 | 0,5 | 1 |
| 4 | 0,333 | 1 | 0,5 | 1 |
| 5 | 0,333 | 1 | 0,5 | 1 |

El documento oficial con la tabla de cinco valores de k no estaba disponible localmente: estos valores salen de las definiciones (para k = 4 y 5 solo hay 3 resultados). Si el material oficial usa k como denominador fijo, los valores de k = 4 y 5 diferirían.

## Consultas sin respuesta

No tienen relevantes, así que Recall, F1 y Hit valen `None`. Quedan **fuera** de los promedios, y el informe indica cuántas se excluyeron. Su comportamiento se registra aparte:

1. **Distancia top‑1** en cada índice, comparada con el rango de los casos con respuesta. Sirve para saber si un umbral de distancia podría detectarlas.
2. **Abstención del generador** (`--abstencion`): se genera la respuesta con la configuración predeterminada y se comprueba si dice «no contiene información suficiente».

## Etiquetado de relevancia

1. Para cada pregunta se leyó el documento fuente y se copiaron **pasajes literales** que la responden. El script falla si un pasaje no aparece en la fuente.
2. Un chunk es relevante si su cuerpo (sin la ruta de encabezados) contiene al menos **40 caracteres consecutivos** de un pasaje, o el pasaje entero si es más corto. La comparación ignora tildes, mayúsculas y espacios.
3. Los IDs se derivan del chunking determinista (sin API) y se verifican contra Chroma (todos existen). **No se consulta el ranking del recuperador.**
4. Una sección es relevante si contiene un chunk relevante. Su ID es `documento_id#ruta de encabezados`.
5. `--etiquetar` congela el dataset (fecha y huella SHA‑256). La evaluación se niega a correr si las etiquetas cambian, y un segundo `--etiquetar` se rechaza. Un test recalcula las etiquetas desde el chunking y exige que coincidan con las congeladas.

Antes de congelar revisé a mano los textos de los 24 conjuntos de etiquetas (12 casos × 2 índices).

## Chunks frente a secciones

| Nivel | Unidad | Se compara con | Configuraciones |
|---|---|---|---|
| A — recuperación original | Los primeros k chunks del ranking | `relevantes.<índice>.chunks` | `indice_original`, `markdown`, `markdown_hibrido` |
| B — contexto expandido | Las k unidades que llegan al generador, identificadas por sección | `relevantes.markdown.secciones` | `markdown_expandido`, `markdown_hibrido_expandido` |

- Las métricas de sección **no** son métricas de chunk: una sección es más grande, así que acertar es más fácil y cada unidad cuesta más contexto.
- Una sección alcanzada por varios chunks cuenta **una vez**. Si una sección supera los 1200 caracteres, llega como dos ventanas distintas que también cuentan como una sola sección. Por eso el denominador de la precisión puede ser menor que k.
- Para cada configuración se registran los caracteres del contexto formateado y los chunks que contiene.

## Cómo repetir la evaluación

```powershell
python -m pytest tests/test_rag_metricas_bloque27.py -v                 # offline
python -m src.evaluar_bloque27 --incluir-hibrido                          # 24 embed_query, sin generación
python -m src.evaluar_bloque27 --incluir-hibrido --abstencion             # + 2 consultas y 2 generaciones
python -m src.evaluar_bloque27 --solo-informe                             # regenera el .md sin API
```

Requisitos: los índices `corpus_proyecto_bloque24` y `corpus_proyecto_bloque24_md` sincronizados con el corpus (`python -m src.indexar_corpus --bloque 24 --plan …` debe mostrar 0 nuevos y 0 huérfanos). No se calculan embeddings de documentos ni se reindexa: `embed_documents=0` en todas las ejecuciones.

## Resultados (dos ejecuciones reales idénticas, 16/11/2026)

Promedios sobre los 10 casos con respuesta; 2 casos sin respuesta excluidos. Detalle en [resultados_evaluacion_bloque27.md](resultados_evaluacion_bloque27.md).

| Configuración | Nivel | k | Precision | Recall | F1 | Hit | Caracteres de contexto |
|---|---|---|---|---|---|---|---|
| `indice_original` | chunk | 3 | 0,367 | 0,800 | 0,490 | 0,800 | 419 |
| | | 5 | 0,240 | 0,850 | 0,367 | 0,900 | 732 |
| `markdown` | chunk | 3 | 0,333 | 0,750 | 0,450 | 0,800 | 734 |
| | | 5 | 0,260 | 0,900 | 0,395 | 0,900 | 1210 |
| **`markdown_expandido`** (CLI predeterminada) | sección | 3 | **0,417** | **0,950** | **0,560** | **1,000** | 2115 |
| | | 5 | 0,300 | 1,000 | 0,444 | 1,000 | 3429 |
| `markdown_hibrido` | chunk | 3 | 0,300 | 0,650 | 0,400 | 0,700 | 714 |
| | | 5 | 0,200 | 0,700 | 0,305 | 0,700 | 1164 |
| `markdown_hibrido_expandido` | sección | 3 | 0,350 | 0,800 | 0,470 | 0,900 | 2148 |
| | | 5 | 0,287 | 1,000 | 0,428 | 1,000 | 3575 |

Interpretación, recomendación y limitaciones en [ensayo-bloque27.md](ensayo-bloque27.md).
