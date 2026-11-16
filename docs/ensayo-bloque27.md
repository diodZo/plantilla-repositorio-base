# Ensayo Bloque 27 — Registro de la evaluación cuantitativa

Fecha: 16 de noviembre de 2026 · Python 3.13.5 · embeddings `models/gemini-embedding-001` · chat `gemini-3.5-flash-lite` (solo para la abstención).

## 1. Inspección inicial

- `git status --short`: `?? src/rag/__init__.py` y `?? src/rag/errores.py`. **Hallazgo:** los commits `6f7a6ed` y `08565c9` incluyen módulos que importan `src.rag.errores`, pero ese archivo y `__init__.py` nunca se añadieron a Git (no están ignorados). Un clon limpio fallaría al importar el paquete RAG. Deben entrar en el próximo commit.
- Colecciones (leídas de Chroma): `corpus_proyecto_bloque24` (recursivo 200/30, 296 chunks, 8 documentos), `corpus_proyecto_bloque24_md` (markdown 200/30, 261 chunks, 8 documentos, 57 secciones) y la experimental `corpus_proyecto_bloque24_c500` (101; no se evalúa). `--plan`: 0 nuevos y 0 huérfanos en las dos evaluadas.
- Metadatos: los 296 + 261 chunks tienen ID determinista, `fuente` y `documento_id`; los del índice markdown tienen además `seccion` e `inicio_cuerpo`. No faltaba ningún identificador.
- Evaluación existente (`src/rag/evaluacion.py`): Hit@k por fuente y por subcadena de evidencia, sin IDs de chunks. Se mantiene sin cambios. El Bloque 27 añade un motor nuevo que reutiliza sus piezas de recuperación.
- Test intermitente del Bloque 26: 3 de 3 ejecuciones de la suite con 207 aprobadas. Sigue sin reproducirse y su causa sigue sin identificarse.

## 2. Dataset

- `data/evaluacion/bloque27_casos.json`: 12 casos. Temas: reintentos y backoff, credenciales, errores de autenticación (sin respuesta), costos, herramientas, memoria, supervisión humana, trazas, indexación y persistencia, recuperación semántica, manejo de errores y una pregunta fuera del corpus.
- El caso **c03** (¿se reintenta un 401?) está **dentro del dominio pero sin respuesta en el corpus**: la política existe solo en `src/cliente.py`, que no está indexado. Es más exigente que una pregunta ajena al proyecto.
- Etiquetado por pasajes literales (método en `README-bloque27.md`). Ensayo en memoria y revisión manual de los 24 conjuntos de etiquetas antes de congelar. Congelado `2026-11-16T22:51:22+00:00`, huella `9e7782ea8474…`. Un segundo `--etiquetar` se rechaza.
- Conjuntos del Bloque 26 (`consultas_recuperacion.json`, `consultas_validacion.json`): clasificados como **históricos**. Se usaron durante el desarrollo y no tienen IDs de chunks, por lo que no se reutilizan para estas métricas.

## 3. Pruebas offline

`python -m pytest tests/test_rag_metricas_bloque27.py -v` → **33 passed**. Cubren: ejemplo oficial y los cinco valores de k, resultados vacíos, relevantes vacíos, duplicados, validación de entradas, valores en [0, 1] y deterministas (200 rankings aleatorios con semilla fija), precisión que sube con k, promedio sin `None`, etiquetado y rechazo de pasajes inventados, coincidencia de las etiquetas congeladas con el chunking determinista, 6 alteraciones del dataset detectadas, chunks frente a secciones, deduplicación de secciones, evaluación de varios casos, peores casos, abstención, historial acumulativo, informe y huella.

Corrección registrada: una parametrización alteraba `casos[2]`, que ya era un caso sin respuesta, así que la mutación no cambiaba nada. Se cambió a `casos[0]`, un caso con pasajes. La validación no se modificó.

## 4. Ejecuciones reales

| Ejecución (UTC) | Comando | embed_query | embed_documents | Generaciones |
|---|---|---|---|---|
| 2026-11-16T22:53:33 | `--incluir-hibrido --abstencion` | 26 | 0 | 2 |
| 2026-11-16T22:53:56 | `--incluir-hibrido` | 24 | 0 | 0 |

**Estabilidad:** rankings y promedios **idénticos** en las dos ejecuciones (0 diferencias en 12 casos × 5 configuraciones × 2 valores de k). Con el índice sin cambios y embeddings de consulta reales, la recuperación fue determinista en esta prueba. Dos ejecuciones no bastan para descartar variaciones del servicio en otras fechas.

## 5. Resultados y análisis

Tabla completa en `README-bloque27.md` y detalle por caso en `resultados_evaluacion_bloque27.md`.

### k=3 frente a k=5

- El recall sube o se mantiene siempre: `indice_original` 0,80 → 0,85; `markdown` 0,75 → 0,90; `markdown_expandido` 0,95 → 1,00.
- La precisión **baja** en los promedios de todas las configuraciones. Pero **no siempre por caso**: en c04 (`markdown_expandido`) sube de 0,500 a 0,667, porque con k=5 entra la segunda sección relevante y dos ventanas de la misma sección del ADR cuentan como una.
- El F1 baja con k=5 en todas las configuraciones: el recall ganado no compensa la precisión perdida.
- El contexto crece de forma considerable: `markdown_expandido` pasa de 2115 a 3429 caracteres (+62 %) para ganar 0,05 de recall (un único caso, c04).

### Chunks frente a secciones

- Las cifras de sección no son comparables uno a uno con las de chunk. Aun así, muestran lo que llega al generador: con `markdown_expandido`, k=3, Hit = 1,0 y Recall = 0,95, frente a 0,80 y 0,75 del mismo índice a nivel de chunk.
- **c05 (herramientas):** a nivel de chunk, Recall@5 = 0 en *todas* las configuraciones sin expansión, aunque los 5 chunks recuperados son del documento correcto (`README-bloque21.md`). Ninguno es una de las dos líneas que nombran las herramientas. La expansión trae la sección «Dominio elegido» completa: es el efecto small‑to‑big.
- **c07 (aprobación):** Recall@3 = 0 en ambos índices a nivel de chunk; 1,0 con expansión. Es el mismo patrón que el escenario B del Bloque 26.
- **c09 (indexación):** con expansión, la precisión baja de 0,667 a 0,333, porque los dos chunks relevantes están en una misma sección (un acierto en lugar de dos).
- **Costo:** la expansión multiplica el contexto por 2,9 respecto de los chunks del mismo índice con k=3 (2115 frente a 734 caracteres) y por 5 respecto del índice original (419). Hay además redundancia: en promedio llegan 2,92 secciones únicas en 3 unidades y 4,67 en 5 unidades, porque las secciones largas llegan como dos ventanas.

### Peores casos

- `indice_original` y `markdown` (k=3): c05 y c07 con Recall = 0.
- `markdown_hibrido`: c05, c06 y c07 con Recall = 0, incluso con k=5. En c06 (memoria), la búsqueda vectorial coloca el chunk relevante en la posición 3. La fusión RRF lo saca del top‑5 en favor de chunks que comparten términos con la pregunta, pero no la responden: «Memoria conversacional», «Arquitectura» del Bloque 22 y «No guardar conversaciones con datos personales…».
- `markdown_expandido` (k=3): c04, con Recall 0,5 (solo una de las dos fuentes); el resto tiene Recall 1.

### BM25/RRF

En este dataset, la híbrida queda **por debajo** de la vectorial en todas las métricas con k=3, con y sin expansión (por ejemplo, Recall@3 por sección: 0,80 frente a 0,95). Con expansión y k=5 empata en Recall y Hit (1,0) y queda por debajo en Precision y F1. Es coherente con lo observado en el Bloque 26 y no se recomienda activarla.

### Casos sin respuesta

| Caso | Distancia top‑1 base / markdown | Generador (`markdown_expandido`, k=3) |
|---|---|---|
| c03 (401, dentro del dominio) | 0,2567 / 0,2990 | Se abstuvo: «La documentación proporcionada no contiene información suficiente para responder.» |
| c12 (base de datos, fuera del dominio) | 0,3322 / 0,3533 | Se abstuvo, pero añadió citas: «… no contiene información suficiente para responder [1][2][3].» |

Rango de distancia top‑1 de los casos con respuesta: base 0,1773–0,2869 y markdown 0,2269–0,2979. Las distancias de c03 caen **dentro** de esos rangos: un umbral de distancia no lo detectaría sin rechazar casos válidos. c12 sí queda por encima en ambos índices. La abstención depende hoy del prompt, y funcionó en 2 de 2 casos (una muestra mínima). Citar fragmentos en una abstención es un defecto menor de formato.

## 6. Recomendación técnica

Mantener la configuración predeterminada de la CLI: **índice markdown + vectorial + expansión por sección, k=3**. En estas mediciones obtiene el mejor F1 (0,560) y el mejor Recall@3 (0,95) de todas las configuraciones, con Hit = 1,0, y unos 2100 caracteres de contexto. Pasar a k=5 solo aportó un caso (c04) a cambio de un 62 % más de contexto y un F1 menor. Usar `--k 5` solo cuando una pregunta mezcle varias fuentes. No activar BM25/RRF con este corpus.

## 7. Limitaciones

- **Tamaño:** 10 casos con respuesta. Cada caso vale 0,1 en Recall o Hit promedio, así que las diferencias de 0,05–0,10 entre configuraciones equivalen a uno o dos casos y no son estadísticamente concluyentes.
- **Independencia:** el dataset lo redactó y etiquetó el desarrollador del sistema durante el desarrollo. Algunos temas se repiten con los conjuntos históricos del Bloque 26. Los pasajes de c09 y c10 vienen de la sección del README escrita durante la consolidación. No hubo evaluadores externos.
- **Criterio de relevancia:** la regla de 40 caracteres es reproducible, pero estricta. Un chunk que parafrasea la respuesta sin copiar el pasaje cuenta como no relevante (c05 a nivel de chunk es un ejemplo de documento correcto con chunk no etiquetado).
- **Recuperación frente a respuesta:** estas métricas miden qué contexto llega al generador, no si la respuesta generada es correcta, completa o bien citada. Un Hit = 1,0 no garantiza una buena respuesta; la calidad de la generación requiere otra evaluación.
- **Abstención:** medida en 2 casos y 1 ejecución.
- **Test intermitente del Bloque 26:** sigue abierto.

## 8. Verificación final

- `python -m pytest tests/test_rag_metricas_bloque27.py -v` → 33 passed.
- `python -m pytest tests/ -v` → **240 passed** (207 previas + 33), 10 warnings de deprecación previas.
- `git diff --check` → sin errores (solo avisos LF→CRLF).
- `git status --short` → modificados `src/rag/expansion.py` y `src/rag/generador.py` (extracción de `expandir_hasta_k`); nuevos los archivos del Bloque 27, más `src/rag/__init__.py` y `src/rag/errores.py`, pendientes desde los Bloques 24–26.
