# Bloque 24 — Indexación del corpus con Chroma y embeddings de Gemini

## Objetivo

Crear un índice vectorial persistente a partir de documentación real del proyecto: carga con metadata de origen, chunking recursivo, embeddings `models/gemini-embedding-001` y almacenamiento en Chroma con IDs estables, sin duplicados al reejecutar.

## Arquitectura

```text
MANIFIESTO_BLOQUE24 (src/rag/corpus.py)
      │  cargar_documentos(): lee los archivos reales, metadata fuente/documento_id/bloque
      ▼
dividir_documentos() (src/rag/chunking.py)
      │  RecursiveCharacterTextSplitter 200/30, chunk_index, chunk_id estable
      ▼
EmbeddingsConReintentos(GoogleGenerativeAIEmbeddings)   (src/rag/embeddings.py)
      │  reintentos solo para 429/5xx/red (reutiliza src/cliente.con_reintento)
      ▼
indexar() (src/rag/indexador.py)
      │  agrega solo IDs ausentes, en lotes de 20 con pausa de 15 s
      ▼
vectorstore/  colección corpus_proyecto_bloque24  (distancia coseno)
```

Detalle de decisiones: [plan-rag-bloques24-26.md](plan-rag-bloques24-26.md).

## Corpus (8 documentos reales, no copiados)

| Fuente | Tema | `bloque` |
|---|---|---|
| `README.md` | Cliente con reintentos, costo referencial | sin asignar |
| `docs/ensayo-bloque13.md` | Backoff, cuota y costos | 13 |
| `docs/decision-arquitectura.md` | ADR: costo y latencia | sin asignar |
| `docs/README-bloque20.md` | Manejo de errores y fallbacks | 20 |
| `docs/README-bloque21.md` | Agente con herramientas | 21 |
| `docs/README-bloque22.md` | Memoria conversacional | 22 |
| `docs/README-bloque23.md` | Supervisión humana | 23 |
| `docs/limites_autonomia_agente.md` | Límites de autonomía | 23 |

`bloque` solo se registra cuando el archivo pertenece inequívocamente a un bloque; si no, la clave se omite.

## Configuración

| Parámetro | Valor | Cómo cambiarlo |
|---|---|---|
| Estrategia | `recursivo` | `--estrategia fijo` |
| `chunk_size` / `chunk_overlap` | 200 / 30 | `--chunk-size`, `--chunk-overlap` |
| Embeddings | `models/gemini-embedding-001` (3072 dimensiones) | `ConfiguracionIndice.modelo_embeddings` |
| Directorio | `<raíz>/vectorstore` (ruta absoluta) | `CONFIG_BLOQUE24` |
| Colección | `corpus_proyecto_bloque24` | `--coleccion` |
| Lote / pausa | 20 textos / 15 s | `--lote`, `--pausa` |
| Credenciales | `GOOGLE_API_KEY` → `GEMINI_API_KEY` → `API_KEY` en `.env` | nunca se imprimen |

IDs: `documento_id = ruta normalizada` (`docs-readme-bloque20-md`) y `chunk_id = {documento_id}:{chunk_index:04d}:{sha256(texto)[:10]}`.

## Comandos (PowerShell, desde la raíz y con `.venv` activado)

```powershell
python -m src.indexar_corpus --bloque 24 --comparar        # compara estrategias; sin API
python -m src.indexar_corpus --bloque 24                   # indexa; usa embeddings reales
python -m src.indexar_corpus --bloque 24 --solo-verificar  # recuento en este y en otro proceso; sin API
python -m src.indexar_corpus --bloque 24 --reconstruir     # borra SOLO esta colección y reindexa
python -m pytest tests/test_rag_chunking.py tests/test_rag_indexacion.py -v
```

## Comparación de estrategias (resultado real, 200/30)

| Estrategia | Chunks | Mín | Máx | Promedio | Cortes a mitad de palabra |
|---|---|---|---|---|---|
| Recursivo | 273 | 8 | 199 | 123,5 | 0 |
| Fijo (`CharacterTextSplitter`, `separator=""`) | 201 | 38 | 200 | 195,8 | 123 |

Ejemplos reales:

- Fijo, chunk 2: `'alida respuestas JSON estructuradas mediante un banco de prompts reutilizable. Además incluye un cliente modular con reintentos y estimación de costos, un pipeline de procesamiento de texto, métricas'` (empieza y termina en mitad de palabra).
- Recursivo, chunks 1–2: `'# Miniaplicación Python — Google Gemini'` y `'Proyecto de la **Especialización en Desarrollo con IA Generativa**'`.

**Elección: recursivo.** No corta palabras (0 frente a 123) y respeta párrafos, líneas y frases. Su costo: más fragmentos (273) y algunos muy cortos (21 chunks de menos de 40 caracteres, casi todos encabezados `## ...`).

## Resultados de indexación real

| Evidencia | Resultado |
|---|---|
| Documentos | 8 |
| Chunks | 273 |
| Primer intento (lotes de 50) | Guardó 100 chunks; el tercer lote falló con **HTTP 429** `RESOURCE_EXHAUSTED` (`embed_content_free_tier_requests`) tras 4 intentos |
| Segundo intento (lotes de 20, pausa de 15 s) | Agregó **solo 173** chunks y reconoció 100 existentes |
| Tercera ejecución | 0 agregados, 273 existentes, **0 embeddings calculados** |
| Persistencia | Directorio existente, 5 archivos, 5 351 588 bytes, recuento 273 |
| Recuento desde otro proceso | 273, consistente |

Las pruebas offline con embeddings **simulados** cubren carga, chunking, metadata, IDs, reindexación, recarga, aislamiento y errores; están en [ensayo-bloque24.md](ensayo-bloque24.md).

## Manejo de errores

Ver la tabla del [plan](plan-rag-bloques24-26.md#5-manejo-de-errores). Los fallos 429/5xx/red se reintentan con backoff (6 intentos, base de 10 s y máximo de 60 s en la CLI). Los errores de autenticación no se reintentan. La lectura no crea colecciones y el índice solo se borra con `--reconstruir`.

## Limitaciones

- Los chunks de 200 caracteres dividen párrafos que deberían permanecer juntos (ver escenario B del Bloque 26).
- El separador `". "` queda al inicio del chunk siguiente (`keep_separator` por defecto), por lo que algunos fragmentos empiezan con `". "`.
- Si se edita un documento del corpus, sus chunks antiguos quedan como «huérfanos»: se informan, pero solo se eliminan con `--reconstruir`.
- La cuota gratuita de embeddings limita la velocidad de indexación; la pausa de 15 s es un valor empírico, no un límite oficial.
