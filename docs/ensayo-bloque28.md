# Ensayo Bloque 28 — Registro de la instrumentación

Fecha: 16 de noviembre de 2026 · Python 3.13.5 · Windows 11 · `gemini-3.5-flash-lite` (`AI_MODEL`) · `models/gemini-embedding-001`.

Los resultados del Bloque 27 (Recall@3 ≈ 0,95, Precision@3 ≈ 0,417, F1 ≈ 0,560) son antecedentes y no se recalcularon.

## 1. Inspección

- `git status --short`: ` M .gitignore`. El cambio sin confirmar es una línea final `tatus --short`, que parece un `git status --short` tecleado por error en el editor. **No se modificó** (es un cambio del usuario), pero el preflight la señala como advertencia. `src/rag/errores.py` y `__init__.py` ya están versionados.
- Embeddings: `crear_embeddings_gemini` → `GoogleGenerativeAIEmbeddings`, envuelto en `EmbeddingsConReintentos`. `embed_query` devuelve solo el vector.
- Generación: `crear_modelo_chat` → `ChatGoogleGenerativeAI(max_retries=0)`; `generador.generar` descartaba el mensaje (y su `usage_metadata`) y devolvía solo el texto. La ruta instrumentada invoca el modelo con el mismo `llamar_con_reintentos` y conserva el mensaje.
- Recuperación: `buscar_con_score` → `similarity_search_with_score`, que en langchain-chroma 1.1.0 calcula `embed_query` internamente. Expansión: `expansion.expandir_hasta_k`. Carga: `indexador.cargar_indice`.
- `.gitignore` excluye `.env`, `.venv/` y `vectorstore/`. `requirements.txt` no requiere cambios: no hay dependencias nuevas.

## 2. Verificaciones previas con la API (llamadas reales)

1. **Tokens del embedding:** se llamó a `client.models.embed_content` con la misma configuración que `embed_query`. Vector idéntico (diferencia máxima 0,0), pero `metadata=None` y `statistics=None`: el proveedor no reporta tokens para embeddings en la API de Gemini.
2. **Tarifas:** consultadas en la página oficial de precios (detalle en `README-bloque28.md`).
3. **Equivalencia de rutas** (`python -m src.registro_rag --comparar-ruta`, 6 `embed_query`): en c01, c07 y c04, la ruta anterior y la instrumentada dieron las **mismas** unidades, distancias (por ejemplo, c07: 0,27407 / 0,294818 / 0,303736) y texto de contexto, con 1 `embed_query` cada una.

## 3. Pruebas offline

`python -m pytest tests/test_rag_latencia.py tests/test_rag_costos.py tests/test_rag_observabilidad.py -v` → **39 passed**. Cubren:

- **Medición:** etapas con reloj falso, total independiente y sobrecarga; etapa fallida con propagación de la excepción; `perf_counter` con `sleep(0.02)`.
- **Costos:** fórmula, `None` cuando faltan tokens o tarifas, valores inválidos, `usage_metadata` con razonamiento y `otros`, tarifas mal configuradas y procedencia de las tarifas del proyecto.
- **Recuperación y consulta instrumentada:** equivalencia de la búsqueda por vector con la búsqueda por texto en Chroma (tmp); 1 `embed_query` y 0 `embed_documents`; mismo contexto que `recuperar()`; contenido en bloques.
- **Fallos:** de red en la generación (4 intentos y estado `error` sin ocultarse) y en el embedding.
- **Registro e informe:** JSONL UTF-8 acumulativo sin la clave ni objetos internos, líneas corruptas informadas, estadísticas con filtro real/simulada, informe solo con datos registrados.
- **Preflight:** `.gitignore`, índice temporal, colección inexistente, modelo de embeddings distinto, tarifas sin modelo y lectura sin modificar el índice.

`python -m pytest tests/ -v` → **279 passed** (240 previas + 39).

## 4. Consultas reales

Configuración: `corpus_proyecto_bloque24_md`, vectorial, expansión, 20 candidatos. Cada fila es una consulta real registrada en `registros_latencia_costo.jsonl`.

| Pregunta (caso del Bloque 27) | k | Embed ms | Búsqueda ms | Generación ms | Total ms | Tokens entrada | Tokens salida | Secciones | Car. contexto | Costo gen. USD |
|---|---|---|---|---|---|---|---|---|---|---|
| c01 reintentos y backoff | 3 | 427,0 | 11,1 | 5317,5 | 5813,7 | 735 | 26 | 3 | 1621 | 0,0002855 |
| c07 aprobación humana | 3 | 364,9 | 3,5 | 761,4 | 1136,2 | 929 | 92 | 3 | 2567 | 0,0005087 |
| c04 costos de API | 3 | 1239,4 | 9,7 | 1056,5 | 2314,3 | 958 | 123 | 2 | 2101 | 0,0005949 |
| c07 aprobación humana | **6** | 406,2 | 4,0 | 945,6 | 1415,8 | **1299** | 92 | 6 | 4073 | 0,0006197 |
| c07 aprobación humana (repetición) | 3 | 1250,8 | 5,7 | 1748,6 | 3058,2 | 929 | 83 | 3 | 2567 | 0,0004862 |

Otras observaciones:

- Expansión: 5,1–10,3 ms. Construcción del prompt: 0,3–10,9 ms (más lenta en la primera consulta de cada proceso). Validación: 0,8–41,7 ms (el primer `count()` de cada proceso es lento). Sobrecarga fuera de etapas: 0,06–0,10 ms.
- Ninguna consulta reportó tokens de razonamiento. En las 5, `total = entrada + salida` (`otros = 0`). Lo verifiqué y no lo supuse.
- 1 intento de generación en todas; sin errores 429 ni de red; `embed_documents = 0` siempre.
- Carga del índice, fuera del total: 1986 ms en la primera ejecución.
- Costo estimado del embedding de consulta: unos 18–19 tokens estimados → ~0,0000028 USD, que no se suma al total.

## 5. Estadísticas (n = 5, ver `resultados_bloque28.md`)

| Medida | Media | Mediana | Mínimo | Máximo |
|---|---|---|---|---|
| Total (ms) | 2747,7 | 2314,3 | 1136,2 | 5813,7 |
| embed_query (ms) | 737,7 | 427,0 | 364,9 | 1250,8 |
| busqueda_vectorial (ms) | 6,8 | 5,7 | 3,5 | 11,1 |
| expansion_contexto (ms) | 7,2 | 7,1 | 5,1 | 10,3 |
| construccion_prompt (ms) | 5,4 | 7,7 | 0,3 | 10,9 |
| generacion (ms) | 1965,9 | 1056,5 | 761,4 | 5317,5 |
| Tokens de entrada | 970 | 929 | 735 | 1299 |
| Tokens de salida | 83,2 | 92 | 26 | 123 |
| Costo de generación (USD) | 0,000499 | 0,000509 | 0,000286 | 0,000620 |
| Caracteres de prompt por token de entrada | 3,99 | 4,13 | 3,54 | 4,15 |

Con 5 consultas, 3 preguntas y 3 procesos distintos, estas cifras **no** representan el rendimiento habitual. La media del total está inflada por la primera generación (5,3 s, arranque en frío); la mediana (2,3 s) es más representativa de esta muestra.

**Reparto del tiempo:** las dos llamadas de red (embedding + generación) representan entre el 95,5 % y el 99,2 % del total. Las etapas locales suman entre 9,9 y 69,2 ms por consulta: búsqueda + expansión + prompt entre 8,9 y 29,1 ms, y validación entre 0,8 y 41,7 ms. La validación es lenta en la primera consulta de cada proceso, que es lo que baja el porcentaje de red en la consulta con k=6.

## 6. Comparación k=3 frente a k=6 (c07)

| Medida | k=3 (dos ejecuciones) | k=6 | Cambio |
|---|---|---|---|
| Tokens de entrada | 929 / 929 | 1299 | **+370 (+40 %)** |
| Secciones / unidades | 3 | 6 | +3 |
| Caracteres de contexto | 2567 | 4073 | +59 % |
| Fuentes | `README-bloque23.md`, `limites_autonomia_agente.md` | las mismas | sin cambio |
| Tokens de salida | 92 / 83 | 92 | variación propia del modelo |
| Costo de generación (USD) | 0,000509 / 0,000486 | 0,000620 | +22 % frente a la primera |
| Total (ms) | 1136 / 3058 | 1416 | no atribuible a k |

- **Los tokens de entrada sí aumentaron.** En esta pregunta, la deduplicación no lo evitó, porque había 6 secciones distintas disponibles entre los 20 candidatos. En otras preguntas podría no ocurrir; la prueba offline `test_k_mayor_puede_no_aumentar_el_contexto` solo exige que no disminuya.
- **La latencia no permite conclusiones:** la repetición con k=3 fue más lenta que k=6. El ruido de red (embedding de 365 a 1251 ms para la misma pregunta) supera el efecto de 370 tokens de entrada adicionales.
- Con k=6 no se añadieron fuentes nuevas, sino más secciones de los mismos documentos. Según el Bloque 27, k=3 ya tenía Recall 0,95 por sección.

## 7. Expansión de contexto: ventajas y desventajas

- **Ventaja** (Bloque 27): mejor recall y Hit al entregar la sección completa.
- **Costo observado aquí:** los tokens de entrada crecen con el tamaño de las secciones (735–1299 tokens por consulta). Como la salida es corta, la entrada pesa en el costo: en c07 con k=3, 929 × 0,30 = 278,7 µUSD de entrada frente a 92 × 2,50 = 230 µUSD de salida. La expansión local en sí cuesta ~5–10 ms, una cifra despreciable frente a la red.

## 8. Recomendaciones

1. Mantener k=3 en la configuración predeterminada: con k=6, la entrada sube un 40 % y el costo un 22 %, sin fuentes nuevas en el caso medido.
2. Para reducir latencia, actuar sobre la red: reutilizar el proceso (evitar el arranque en frío), considerar *streaming* para la percepción del usuario y cachear embeddings de preguntas repetidas. Optimizar la parte local no rinde.
3. Si el costo de entrada importa, usar `--max-contexto` o un `--max-seccion` menor; medir su efecto en la recuperación con la evaluación del Bloque 27 antes de adoptarlo.
4. Para afirmaciones de rendimiento, repetir cada pregunta varias veces en un mismo proceso y descartar la primera consulta.

## 9. Limitaciones

- Muestra mínima (5 consultas): sin estadística inferencial. La latencia de red varía mucho entre ejecuciones.
- El costo es una estimación a tarifa de pago. El importe facturado se desconoce (probable nivel gratuito) y no incluye caché ni descuentos.
- Los tokens del embedding no los reporta el proveedor: solo hay una estimación.
- Las tarifas se obtuvieron de la página oficial mediante una herramienta de consulta web que resume el contenido. La página no tiene fecha de actualización: hay que verificarlas antes de usarlas para presupuestos.
- La etapa `busqueda_vectorial` incluye un segundo `count()` local de validación (dentro de `buscar_por_vector_con_score`).
- El test intermitente del Bloque 26 sigue abierto (ver la sección 10).

## 10. Verificación final

- `python -m pytest tests/ -v` → **279 passed** (las 240 anteriores + 39 de este bloque).
- `git diff --check` → sin errores (solo avisos LF→CRLF).
- `git status --short` → modificados `.gitignore` (línea `registros_latencia_costo.jsonl` añadida; la línea `tatus --short` del usuario sigue ahí) y `src/rag/recuperador.py` (solo la función nueva); nuevos los archivos del Bloque 28.
- `python -m src.rag.preflight` → 0 errores y 1 advertencia (la línea `tatus --short`).

### Test intermitente (sigue abierto, con nueva evidencia)

Durante las verificaciones, la suite completa falló 1 vez en 3 ejecuciones y otra vez en la iteración 13 de un bucle de 15. Esta vez se capturó la traza: el fallo apareció en `test_rag_consolidacion.py::test_expansion_y_limite_conservan_citas` (no en el test señalado en el Bloque 26), con

`chromadb.errors.InternalError: Error executing plan: Internal error: Error creating hnsw segment reader: Nothing found on disk`

lanzado por `collection.query` dentro de `buscar_con_score`. Ambos tests usan el fixture `indices_temporales`, que indexa dos colecciones en un directorio temporal y consulta de inmediato.

**Hipótesis no confirmada:** una condición de carrera de Chroma 1.5.9 entre la escritura del segmento HNSW y su lectura inmediata. Un script de estrés fuera de pytest (60 iteraciones con una colección y 60 con dos, indexando y consultando de inmediato) dio **0 fallos**, así que también podría intervenir el estado compartido de los clientes de Chroma entre tests del mismo proceso. No se aplicó ninguna corrección: un reintento ante `InternalError` ocultaría el síntoma sin explicarlo. El error no proviene del código del RAG, pero mientras no se aclare, conviene no consultar un índice en el mismo instante en que se termina de crear.
