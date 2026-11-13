# Ensayo Bloque 25 — Registro de la réplica

Fecha: 12 de noviembre de 2026.

## Pasos ejecutados

1. Búsqueda del material oficial en `D:\Repositorios\curso\` (incluidas `respaldo-plantilla-base` y `Nueva carpeta`): **no encontrado**. Se crearon cinco textos propios en `data/corpus/tienda/`, documentados como no oficiales.
2. `python -m src.indexar_corpus --bloque 25 --comparar`: recursivo y fijo → 5 chunks (86/113/99); no hay cortes porque ningún texto supera 150 caracteres.
3. `python -m src.indexar_corpus --bloque 25`: `agregados=5`, `conteo_final=5`, 5 textos en 1 llamada real a `models/gemini-embedding-001`; verificación `{"archivos": 5, "bytes": 1493156, "conteo": 5, "consistente": true}`; otro proceso: 5.
4. Reejecución: `agregados=0`, `ya_existentes=5`, 0 textos embebidos.
5. `python -m src.indexar_corpus --bloque 24 --solo-verificar`: 273 (el índice del Bloque 24 no fue afectado).
6. Tres consultas reales con paráfrasis sobre el índice recargado: las tres recuperaron primero el documento correcto (ver [README-bloque25.md](README-bloque25.md)). `embed_documents=0`.

## Pruebas offline relacionadas (embeddings SIMULADOS)

- `test_bloque25_produce_cinco_chunks_sin_vacios_ni_duplicados`
- `test_colecciones_aisladas_en_el_mismo_directorio`
- `tests/test_rag_recuperacion.py` y `tests/test_rag_prompts.py` usan este corpus en `tmp_path`.

## Aprendizaje

La réplica solo requirió una configuración y un manifiesto nuevos: el resto del código se reutilizó sin cambios, lo que confirma la separación de responsabilidades del Bloque 24.
