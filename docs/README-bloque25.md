# Bloque 25 — Réplica guiada sobre otro corpus

## Objetivo

Reutilizar la arquitectura del Bloque 24 con otro corpus: cinco políticas de una tienda ficticia, `chunk_size=150`, `chunk_overlap=20`, en un directorio y una colección distintos.

## Corpus

`data/corpus/tienda/01_cancelacion.txt` … `05_envio_devoluciones.txt` (cinco temas: cancelación en 24 h, devolución en 30 días sin usar, reembolso en 5–10 días hábiles, excepciones en ofertas, envío de devoluciones).

> **Importante:** el documento oficial del curso con los cinco textos **no estaba disponible localmente**. Los textos se redactaron para esta réplica (ver [data/corpus/tienda/LEEME.md](../data/corpus/tienda/LEEME.md)). El resultado de cinco chunks se verifica para estos textos; no se afirma que coincida con el material oficial. Para usar los oficiales, basta con reemplazar los cinco archivos.

## Reutilización (sin duplicar lógica)

| Paso | Función compartida |
|---|---|
| Cargar documentos | `cargar_documentos(MANIFIESTO_BLOQUE25)` |
| Chunking | `dividir_documentos(..., "recursivo", 150, 20)` |
| Embeddings | `EmbeddingsConReintentos(crear_embeddings_gemini())` |
| Indexar | `indexar(chunks, CONFIG_BLOQUE25, ...)` |
| Cargar índice | `cargar_indice(CONFIG_BLOQUE25, ...)` |
| Verificar persistencia | `verificar_persistencia`, `contar_en_otro_proceso` |

Lo único específico del bloque es `CONFIG_BLOQUE25` (`vectorstore_ejemplo/`, colección `politicas_tienda_bloque25`, 150/20) y `MANIFIESTO_BLOQUE25`.

## Comandos

```powershell
python -m src.indexar_corpus --bloque 25 --comparar
python -m src.indexar_corpus --bloque 25
python -m src.indexar_corpus --bloque 25 --solo-verificar
python -m pytest tests/test_rag_chunking.py -k bloque25 -v
```

## Resultados reales

| Evidencia | Resultado |
|---|---|
| Documentos | 5 |
| Chunks (150/20, recursivo y fijo) | **5** (mín 86, máx 113, promedio 99) |
| Chunks vacíos / duplicados | 0 / 0 (`validar_chunks` y test `test_bloque25_produce_cinco_chunks_sin_vacios_ni_duplicados`) |
| Primera indexación | 5 agregados, 5 textos en 1 llamada |
| Reindexación | 0 agregados, 0 embeddings |
| Persistencia | 5 archivos, 1 493 156 bytes, recuento 5 en este proceso y en otro |
| Aislamiento | La colección del Bloque 24 siguió con 273 chunks |

Consultas reales sobre el índice recargado (sin reindexar: `embed_documents=0`, `embed_query=3`), con otras palabras:

| Pregunta | 1.ª fuente (distancia) | 2.ª fuente |
|---|---|---|
| ¿Me devuelven la plata si compré algo rebajado? | `04_ofertas.txt` (0,2286) | `01_cancelacion.txt` (0,2588) |
| ¿Cuánto demora en volver el dinero a mi tarjeta? | `03_reembolso.txt` (0,2500) | `02_devolucion.txt` (0,3234) |
| Me arrepentí de la compra que hice esta mañana | `01_cancelacion.txt` (0,2272) | `04_ofertas.txt` (0,2782) |

## Limitaciones

Con textos de menos de 150 caracteres, el chunking no tiene efecto (un chunk por documento) y ambas estrategias coinciden. La réplica no se registra en un commit independiente.
