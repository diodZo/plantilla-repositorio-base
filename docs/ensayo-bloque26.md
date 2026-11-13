# Ensayo Bloque 26 — Registro de consultas

Fecha: 12 de noviembre de 2026 · embeddings `models/gemini-embedding-001` · chat `gemini-3.5-flash-lite` (`AI_MODEL` de `.env`).

## Pruebas offline (sin Gemini)

```powershell
python -m pytest tests/test_rag_recuperacion.py tests/test_rag_prompts.py -v
```

**28 passed** (16 + 12, contando parametrizaciones). Cubren `k` configurable (1, 2, 3, 5), pertinencia con embeddings SIMULADOS, cambio de resultados según la pregunta, distancias ordenadas en 0–2, ausencia de `embed_documents` durante la consulta, índice vacío, parámetros inválidos, dimensión incompatible, contexto numerado, diccionario de citas, metadata faltante, prompt con reglas y pregunta intacta, inyección dentro de documentos, respuesta sin contexto sin invocar el modelo (`FakeListChatModel`/doble) y contenido en bloques.

## Ejecuciones reales

| Comando | Llamadas reales | Resultado |
|---|---|---|
| `python -m src.recuperar_corpus --escenarios` | 5 `embed_query` + 3 generaciones | A pertinente, B insuficiente (fallo de recuperación), C insuficiente (correcto) |
| Ídem con `--coleccion corpus_proyecto_bloque24_c500 --chunk-size 500 --chunk-overlap 75` | 5 + 3 | A mejor (cita backoff), B y C insuficientes |
| `python -m src.recuperar_corpus "¿El costo que calcula el cliente modular corresponde a la tarifa oficial de Gemini?"` | 3 + 1 | Respuesta correcta con [1][2] |
| `python -m src.recuperar_corpus "¿Qué herramienta del agente necesita que una persona la autorice antes de ejecutarse?" --k 6` | 3 + 1 | Insuficiente; ninguna de las 6 fuentes contenía la respuesta |

Las fuentes, las distancias y las respuestas literales están en [README-bloque26.md](README-bloque26.md).

## Verificación manual

- B2 [1] = `README.md` línea 142: «El cliente modular `src/cliente.py` incorpora un costo **referencial** por tokens, con una tarifa ilustrativa que no corresponde al precio oficial de Gemini.» ✔
- B2 [2] = `docs/ensayo-bloque13.md` línea 21: «El costo por 1000 tokens del ejemplo es **didáctico**, no corresponde necesariamente a la tarifa vigente de Gemini» ✔
- B: la respuesta existe en `docs/limites_autonomia_agente.md` línea 13 («La simulación de reembolso sí pide una decisión humana explícita `s`»), pero no fue recuperada.

## Errores y advertencias observados

- `UserWarning: Model 'gemini-3.5-flash-lite' uses fixed sampling defaults; the sampling parameter(s) temperature will be ignored` → se eliminó `temperature=0` de `crear_modelo_chat`.
- No hubo errores 429 durante las consultas.

## Conclusión

El pipeline cumple con recuperar sin reindexar, citar con fuentes reales y abstenerse cuando el contexto no alcanza (B y C). El fallo de B muestra que el prompt evita alucinaciones, pero no compensa una recuperación deficiente: la mejora pendiente está en la etapa de recuperación.

---

# Optimización del recuperador — registro (12 de noviembre de 2026)

## Diagnóstico (llamadas reales: solo `embed_query`)

1. `almacen.get(where={"fuente": "docs/limites_autonomia_agente.md"})` → 26 chunks. Los chunks 5–9 contienen el párrafo de la línea 13 dividido: `## Supervisión humana` | `Las dos herramientas de orientación no requieren aprobación` | `. La simulación de reembolso sí pide una decisión humana explícita …` | `. El resultado de la decisión …` | `. Esta aprobación no representa …`.
2. `similarity_search_with_score(B, k=273)`: chunk 7 en la posición 28 (0,3384); chunk 6 en la 10 (0,3025); chunk 9 en la 14 (0,3173); chunk 5 en la 32 (0,3421).
3. Colección 500/75: el párrafo completo está en la posición 10 (0,3041) y la sección de diseño de `README-bloque23.md`, en la 12.
4. Índice completo: 21 chunks de menos de 40 caracteres (19 encabezados aislados; los otros 2 son `'el historial siempre recibe un `str`:'` y `'. No se cambió ninguna otra versión.'`) y 52 de 273 chunks que empiezan con `". "`.

## Implementación

- `src/rag/lexico.py`: BM25 Okapi (k1=1,5, b=0,75), construido con `almacen.get()` sin embeddings.
- `src/rag/hibrido.py`: `fusionar_rrf` (deduplicación por ID y metadatos intactos) y `buscar_hibrido`.
- `src/rag/chunking.py`: estrategia `markdown` (secciones, ruta de encabezados, `keep_separator="end"`). `comparar_estrategias` mantiene por defecto `("recursivo", "fijo")`.
- `src/rag/expansion.py`: *small-to-big* por sección o ventana de vecinos.
- `src/rag/generador.py`: `recuperar(modo, expandir, candidatos)`; `responder` acepta los mismos parámetros y por defecto se comporta como antes.
- `src/rag/evaluacion.py` y `src/evaluar_recuperacion.py`: Hit@k estricto y por fuente.
- CLI: `--indice`, `--modo` y `--expandir` en `src/recuperar_corpus.py`; `--coleccion` y `--estrategia markdown` en `src/indexar_corpus.py`.

## Pruebas

`python -m pytest tests/ -v` → **194 passed** (176 previas + 18 en `tests/test_rag_hibrido.py`), 10 warnings de deprecación previas. Ninguna prueba previa fue eliminada ni modificada.

Ajuste registrado: en `test_recupera_informacion_de_supervision_humana`, la primera versión comprobaba también el modo vectorial con embeddings **simulados** y falló, porque la bolsa de palabras por hash no es semántica. La prueba se limitó al modo híbrido (BM25 real); el modo vectorial real se mide con Gemini en la evaluación.

## Ejecuciones reales

| Comando | Llamadas a la API | Resultado |
|---|---|---|
| `python -m src.evaluar_recuperacion --salida docs/evaluacion_recuperacion_v1.json` | 9 `embed_query` | Hit@3 evidencia: vectorial 0,714, léxica 0,571, híbrida 0,571. B no aparece en el top‑20 con ningún método |
| `python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md` | 242 textos / 13 llamadas | 242 chunks; recuento 242 en otro proceso. El motivo quedó registrado antes en `plan-rag-bloques24-26.md` §7 |
| `evaluar_recuperacion` sobre `markdown` | 9 | Igual que la base (0,714 / 0,571 / 0,571); B >20 |
| `evaluar_recuperacion --expandir` (base, ventana) | 9 | 0,857 / 0,857 / 0,714; B en las posiciones 10 / 2 / 6 |
| `evaluar_recuperacion --expandir` sobre `markdown` | 9 | **1,0 / 1,0 / 1,0**; B en las posiciones 2 / 1 / 2 |
| `recuperar_corpus --escenarios --indice markdown --expandir` | 5 `embed_query` + 3 generaciones | A correcto (cita el backoff), **B respondido con cita [2] a `docs/limites_autonomia_agente.md`**, C con abstención |
| Ídem `--modo hibrido` | 5 + 3 | B respondido y C con abstención; A omitió el backoff |
| `recuperar_corpus --escenarios --sin-generar` (por defecto) | 5 | Mismas fuentes y distancias que la línea base: compatibilidad confirmada |

En todas las consultas: `embed_documents=0`.

## Conclusión

El escenario B queda resuelto con una recuperación real, pero solo con la combinación de **chunking por secciones + expansión small-to-big**. La búsqueda híbrida (BM25 + RRF) quedó implementada y probada, aunque las mediciones muestran que por sí sola no corrige B y que en este corpus no supera a la vectorial. La causa raíz era la fragmentación del contexto, no el método de búsqueda.

---

# Consolidación — registro (12 de noviembre de 2026)

## Diagnóstico final del escenario B

La respuesta (`docs/limites_autonomia_agente.md`, línea 13) siempre estuvo indexada. El chunking recursivo de 200 caracteres partió el párrafo en 5 fragmentos sin contexto, y la frase clave quedó en la posición 28. Ni la búsqueda léxica (vocabulario distinto) ni la híbrida lo resolvieron. Lo resolvió la combinación de: (a) chunks por sección con la ruta de encabezados y (b) expansión de cada chunk a su sección completa. Con la configuración predeterminada, la sección correcta queda en la posición 2 y la respuesta se cita correctamente.

## Cambios

- La CLI `src/recuperar_corpus.py` usa por defecto `--indice markdown`, `--modo vectorial` y la expansión activada. Nuevas opciones: `--sin-expandir`, `--max-seccion` y `--max-contexto`. Imprime las métricas de cada consulta.
- `src/rag/generador.py`: `aplicar_limite_contexto`, `calcular_metricas` y `preparar_contexto`; `responder(..., max_contexto=None)` devuelve `metricas`. Los valores por defecto de la API no cambiaron.
- `src/rag/prompts.py`: reglas 6 (redacción clara y gramatical) y 7 (identificadores exactos solo si están en el contexto).
- `src/rag/indexador.py` y `src/indexar_corpus.py`: `planificar_indexacion` / `--plan` (sin API) y `podar_huerfanos` / `--podar-huerfanos` (solo la colección indicada).
- `data/evaluacion/consultas_validacion.json` (6 + 2 consultas); `src/evaluar_recuperacion.py` con `--conjunto` e `--indice`.
- `README.md`: nueva sección final «RAG sobre la documentación del proyecto (Bloques 24–26)».

## README.md en el corpus

1. `--plan` antes de editar: 0 nuevos y 0 huérfanos en `corpus_proyecto_bloque24` (273) y en `corpus_proyecto_bloque24_md` (242).
2. Se agregó la sección **al final** del archivo para no desplazar los `chunk_index` existentes.
3. `--plan` después: base +23 / 0 huérfanos; markdown +19 / 0 huérfanos (solo `README.md`).
4. `--podar-huerfanos` en ambas: 23 textos en 2 llamadas y 19 en 1 llamada; recuentos 296 y 261, consistentes desde otro proceso; `podados=0`.
5. `corpus_proyecto_bloque24_c500` no se actualizó (experimental; `--plan` indica 8 pendientes). `politicas_tienda_bloque25`: 5, sin cambios.

## Pruebas

`python -m pytest tests/ -v` → **207 passed** (194 previas + 13 en `tests/test_rag_consolidacion.py`), 10 warnings de deprecación previas. No se eliminó ni se modificó ninguna prueba anterior.

## Evaluación real (índices actualizados)

| Ejecución | `embed_query` | Hit@3 evidencia (vect. / léx. / híbr.) |
|---|---|---|
| `--conjunto desarrollo` (base) | 9 | 0,714 / 0,571 / 0,571 (igual que antes de editar `README.md`; en la híbrida, `supervision-2` pasó de la posición 14 a la 13) |
| `--conjunto desarrollo --indice markdown --expandir` | 9 | 1,0 / 1,0 / 1,0 |
| `--conjunto validacion` (base) | 8 | 0,833 / 0,333 / 0,500 |
| `--conjunto validacion --indice markdown --expandir` | 8 | 1,0 / 0,833 / 1,0 |

## Consultas reales con generación (configuración predeterminada)

`python -m src.recuperar_corpus --escenarios` (5 `embed_query`, 3 generaciones, `embed_documents=0`): A cita el 429 y el backoff; B es gramaticalmente correcta y cita `docs/limites_autonomia_agente.md`; C se abstiene. Ninguna cita inválida. `python -m src.recuperar_corpus "¿Cómo se detecta …?" --max-contexto 1500`: 1 unidad incluida y 2 omitidas; la respuesta usa el identificador `detectar_repeticiones`, presente en el contexto. Textos literales y métricas en `README-bloque26.md`.

## Limitaciones vigentes

- Las 7 consultas de desarrollo guiaron el diseño; su 1,0 no demuestra generalización. La validación (6 consultas, mismo autor) es favorable pero pequeña.
- Sin umbral de distancia: fuera del corpus siempre hay contexto, y la abstención depende del modelo.
- La expansión triplica, o más, el contexto. `--max-contexto` lo acota, pero puede dejar fuera unidades útiles.
- Las respuestas siguen siendo probabilísticas; las métricas verifican la forma de las citas, no su veracidad.

## Prueba intermitente (abierta)

`tests/test_rag_consolidacion.py::test_cli_modo_predeterminado_sin_reindexar_y_con_metricas` falló **2 veces en unas 41 ejecuciones** de la suite completa (sin traza capturada en la primera; la segunda solo informó el nombre). No falló en 8 ejecuciones aisladas ni en 25 ejecuciones consecutivas de la suite completa. Se descartó que el orden de resultados con embeddings simulados variara (6 índices nuevos dieron el mismo ranking). **La causa sigue sin identificarse.** Las aserciones ahora incluyen la salida completa de la CLI para diagnosticar la próxima ocurrencia. La última ejecución de `python -m pytest tests/ -v`: 207 passed.
