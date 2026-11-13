# Ensayo Bloque 24 — Registro de ejecución

Fecha: 12 de noviembre de 2026 · Python 3.13.5 · Windows 11 · `.venv` del proyecto.

## Dependencias

Instaladas en esta sesión: `langchain-chroma 1.1.0`, `chromadb 1.5.9` (con `numpy 2.5.4` y `onnxruntime 1.31.1`). Ya presentes: `langchain-core 1.7.4`, `langchain-google-genai 4.4.2`, `langchain-text-splitters 1.1.3` y `python-dotenv 1.2.4`. `pip check`: *No broken requirements found*.

## Pruebas offline (sin Gemini, embeddings SIMULADOS)

```powershell
python -m pytest tests/test_rag_chunking.py tests/test_rag_indexacion.py -v
```

Resultado: 15 + 27 = **42 passed**. Usan `EmbeddingsSimuladasBolsaPalabras` (`tests/conftest.py`), un vector de bolsa de palabras por hash que **no es un modelo semántico**, y directorios `tmp_path` de pytest. No escriben en `vectorstore/`.

## Ejecuciones reales (Gemini)

1. `python -m src.indexar_corpus --bloque 24 --comparar`: sin API. Recursivo: 273 chunks (8/199/123,5, 0 cortes de palabra). Fijo: 201 chunks (38/200/195,8, 123 cortes).
2. `python -m src.indexar_corpus --bloque 24` (primera versión, lotes de 50): `Error (ErrorTransitorio)` después de reintentos a los 4,1 s, 8,0 s y 17,2 s. El diagnóstico de la causa mostró `ClientError 429 RESOURCE_EXHAUSTED ... Quota exceeded for metric: generativelanguage.googleapis.com/embed_content_free_tier_requests`. El índice conservó los 2 lotes que alcanzaron a completarse (100 chunks).
3. Prueba de lotes reales: 1, 5 y 20 textos → OK, dimensión **3072**.
4. Se agregaron `--lote` (20) y `--pausa` (15 s), además de un mensaje de error con el código de la causa. Reejecución: `agregados=173`, `ya_existentes=100`, `conteo_final=273`, 173 textos en 9 llamadas. Verificación: `{"directorio_existe": true, "archivos": 5, "bytes": 5351588, "conteo": 273, "esperado": 273, "consistente": true}` · otro proceso: 273, consistente.
5. Nueva reejecución: `agregados=0`, `ya_existentes=273`, **0 textos embebidos**.
6. `--solo-verificar` (proceso nuevo, sin API): 273 en ambos procesos, código de salida 0.
7. Experimento: `--chunk-size 500 --chunk-overlap 75 --coleccion corpus_proyecto_bloque24_c500` → 101 chunks (56/499/342,0), 101 textos en 6 llamadas, consistente en otro proceso. Comparación fija con 500/75: 82 chunks y 44 cortes de palabra. Esta colección es experimental y comparte el directorio `vectorstore/`, aislada por nombre.

## Errores observados

- HTTP 429 de cuota gratuita de embeddings con lotes de 50 (real). Se resolvió con lotes más pequeños y pausas, y la reanudación evitó recalcular lo ya guardado.
- Advertencia del modelo de chat: `temperature` es ignorada por `gemini-3.5-flash-lite`; se quitó ese parámetro.

## Conclusión

El índice es reproducible: IDs deterministas, reejecuciones idempotentes, persistencia verificada desde otro proceso y recuperación ante una cuota agotada sin perder el trabajo hecho.
