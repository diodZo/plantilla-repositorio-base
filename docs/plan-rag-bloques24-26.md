# Plan de implementación RAG — Bloques 24, 25 y 26

Fecha: 12 de noviembre de 2026.

## 1. Estado inicial observado

- `git status --short`: árbol limpio (último commit `613c016`, Bloque 23).
- Suite previa: `python -m pytest tests/ -q` → **106 passed**, 10 warnings (deprecaciones de LangChain), sin llamadas reales.
- Python 3.13.5 en `.venv`.
- Dependencias ya instaladas: `langchain-core 1.7.4`, `langchain-google-genai 4.4.2`, `langchain-text-splitters 1.1.3`, `python-dotenv 1.2.4`.
- Faltaban `langchain-chroma` y `chromadb`; se instalaron `langchain-chroma 1.1.0` y `chromadb 1.5.9` (arrastra `numpy 2.5.4` y `onnxruntime 1.31.1`).
- Credenciales: `.env` en la raíz con `API_KEY` y `AI_MODEL`. Los bloques 19–23 aceptan además `GOOGLE_API_KEY` y `GEMINI_API_KEY` (en ese orden de prioridad). El RAG reutiliza la misma convención y nunca imprime la clave.
- `.gitignore` excluía `.env`, `.venv/` y `trazas_agente_bloque23.jsonl`, pero no los directorios de índices.
- No se encontró localmente el documento oficial del curso de los Bloques 24–26 (se revisaron `D:\Repositorios\curso\`, `respaldo-plantilla-base` y `Nueva carpeta`).

## 2. Módulos previos reutilizados

| Módulo previo | Uso en el RAG |
|---|---|
| `src/cliente.py::con_reintento` | Backoff exponencial con jitter. Solo reintenta `TimeoutError`; el RAG traduce los fallos transitorios (429, 5xx, red) a una subclase de `TimeoutError`, de modo que la política de reintentos es la misma del Bloque 13. Los errores de autenticación nunca se convierten y, por tanto, no se reintentan. |
| Convención de `.env` de los Bloques 19–23 | `GOOGLE_API_KEY` → `GEMINI_API_KEY` → `API_KEY`; `AI_MODEL` para el modelo de chat. |

No se modifica ningún archivo de bloques anteriores.

## 3. Arquitectura

```text
src/rag/
  errores.py        Jerarquía de excepciones del RAG (ErrorRAG y subclases)
  configuracion.py  Rutas absolutas, ConfiguracionIndice, lectura segura de credenciales
  corpus.py         Manifiestos de corpus y carga de documentos con metadata de origen
  chunking.py       Splitters fijo/recursivo, IDs estables, estadísticas y validación
  reintentos.py     Clasificación de errores y reintentos (reutiliza src/cliente.py)
  embeddings.py     GoogleGenerativeAIEmbeddings + envoltorio con reintentos y contadores
  indexador.py      Indexación idempotente en Chroma, carga y verificación de persistencia
  recuperador.py    similarity_search, with_score, as_retriever y formatear_contexto
  prompts.py        Prompt dinámico con citas y contexto tratado como datos
  generador.py      Generación separada: recuperar → construir prompt → invocar modelo
src/indexar_corpus.py    CLI Bloques 24/25: comparar, indexar, verificar
src/recuperar_corpus.py  CLI Bloque 26: consultas y escenarios A/B/C
data/corpus/tienda/      Cinco textos del ejercicio del Bloque 25
```

Las responsabilidades quedan separadas y se inyectan dependencias (embeddings, modelo, funciones de espera) para que todo sea comprobable sin red.

## 4. Decisiones

### Corpus del Bloque 24

Se indexan **documentos reales del repositorio en su ubicación original** (no se copian a `data/corpus/`), para que la metadata `fuente` apunte al archivo verdadero y no exista una segunda copia que pueda desincronizarse. El manifiesto `MANIFIESTO_BLOQUE24` de `src/rag/corpus.py` declara cada archivo y su bloque:

| Fuente | Tema | Bloque |
|---|---|---|
| `README.md` | Cliente con reintentos, costo referencial, estructura general | sin asignar (abarca varios bloques) |
| `docs/ensayo-bloque13.md` | Backoff, cuota y costos | 13 |
| `docs/decision-arquitectura.md` | ADR, costo estimado y latencia | sin asignar (ADR) |
| `docs/README-bloque20.md` | Manejo de errores y fallbacks | 20 |
| `docs/README-bloque21.md` | Agente con herramientas | 21 |
| `docs/README-bloque22.md` | Memoria conversacional | 22 |
| `docs/README-bloque23.md` | Supervisión humana y trazas | 23 |
| `docs/limites_autonomia_agente.md` | Límites de autonomía | 23 |

`bloque` solo se guarda cuando el archivo pertenece inequívocamente a un bloque; en caso contrario la clave se omite (Chroma no admite `None`), en vez de inventar un valor.

### Chunking

- Dos estrategias comparables: `CharacterTextSplitter(separator="")` (corte por tamaño fijo) y `RecursiveCharacterTextSplitter` con separadores `["\n\n", "\n", ". ", " ", ""]`.
- Valores iniciales `chunk_size=200`, `chunk_overlap=30`, configurables por CLI.
- Se indexa con la estrategia **recursiva**: respeta párrafos, líneas y frases, y no corta palabras a la mitad. La justificación con cifras reales queda en `docs/README-bloque24.md`.

### Identificadores y duplicados

- `documento_id`: ruta relativa normalizada (`docs/README-bloque20.md` → `docs-readme-bloque20-md`).
- `chunk_id`: `{documento_id}:{chunk_index:04d}:{sha256(texto)[:10]}`. Es determinista y cambia si cambia el contenido.
- Antes de agregar, se consultan los IDs ya presentes y **solo se calculan embeddings de los nuevos**. Una reindexación sin cambios no consume cuota ni duplica.
- Los IDs presentes en la colección que ya no existen en el corpus se informan como «huérfanos»; solo se eliminan con `--reconstruir`.
- `--reconstruir` es la única vía que borra una colección, y solo la colección indicada.

### Chroma

- `vectorstore/` (Bloque 24, colección `corpus_proyecto_bloque24`) y `vectorstore_ejemplo/` (Bloque 25, colección `politicas_tienda_bloque25`), con rutas absolutas basadas en la raíz del repositorio.
- Distancia **coseno** (`hnsw:space=cosine`). La metadata de la colección guarda modelo de embeddings, estrategia, `chunk_size` y `chunk_overlap`. Al cargar o reindexar se valida que coincidan; si no, se lanza un error explícito.
- La lectura (`cargar_indice`) nunca crea colecciones: si la colección no existe, informa el error en lugar de crear una vacía.

### Embeddings

- `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")` con la clave obtenida de `.env`.
- `EmbeddingsConReintentos` envuelve cualquier `Embeddings`, aplica reintentos solo a fallos transitorios y cuenta llamadas a `embed_documents`/`embed_query` (permite demostrar que una consulta no reindexa).
- Las pruebas usan `EmbeddingsSimuladasBolsaPalabras` (definida en `tests/conftest.py`), identificada como **simulación**.

### Bloque 25

El documento oficial con los cinco textos de la tienda **no está disponible localmente**. Se redactan cinco textos breves sobre los cinco temas indicados en el enunciado (cancelación 24 h, devolución 30 días, reembolso 5–10 días hábiles, excepciones en ofertas, costo de envío de devoluciones) y se documenta que **no son los textos oficiales**. Por ello, el resultado esperado de cinco chunks con `150/20` se verifica para estos textos, pero no puede afirmarse que coincida con el material.

### Bloque 26

- `recuperador.py`: `buscar`, `buscar_con_score`, `crear_retriever` y `formatear_contexto`. `k=3` configurable. Se comprueba que la colección no esté vacía antes de consultar.
- El score de Chroma es una **distancia coseno** (0 = idéntico, mayor = menos similar); no se convierte en porcentaje.
- `formatear_contexto` devuelve `("[1] ...\n\n[2] ...", {1: "docs/...", ...})`. Si un documento carece de `fuente`, lanza `MetadataFaltanteError` indicando la posición.
- `prompts.py` construye un `ChatPromptTemplate` con reglas de uso exclusivo del contexto, citas numeradas, reconocimiento de insuficiencia, prohibición de inventar fuentes y contexto delimitado como datos. La pregunta se pasa sin modificar.
- `generador.py` mantiene separadas recuperación, prompt y generación. Si no hay documentos recuperados, responde con un mensaje fijo sin llamar al modelo.

## 5. Manejo de errores

| Situación | Tratamiento |
|---|---|
| Credenciales faltantes | `CredencialesFaltantesError` antes de cualquier llamada |
| Credenciales inválidas (400 API_KEY_INVALID, 401, 403) | `CredencialesInvalidasError`, sin reintentos |
| 429 / 5xx / errores de conexión o timeout | `ErrorTransitorio` (subclase de `TimeoutError`) → backoff de `src/cliente.py` |
| Dependencias ausentes | `DependenciaFaltanteError` con el comando de instalación |
| Directorio sin escritura | `DirectorioNoEscribibleError` |
| Índice vacío | `IndiceVacioError` |
| Colección inexistente | `ColeccionInexistenteError` (no se crea al leer) |
| Embeddings incompatibles (modelo o dimensión) | `EmbeddingsIncompatiblesError` |
| Configuración de chunking distinta | `ConfiguracionIncompatibleError` (sugiere `--reconstruir`) |
| Documento sin metadata | `MetadataFaltanteError` |
| Documentos duplicados (ruta o contenido) | `DocumentoDuplicadoError` |
| Sin resultados recuperados | Respuesta fija «sin información suficiente», sin llamar al modelo |

No se usan `except Exception` para ocultar errores de programación.

## 6. Fases

1. Inspección y plan (este documento).
2. Bloque 24: corpus, chunking, embeddings, indexación y verificación desde otro proceso.
3. Bloque 25: réplica con el mismo código y otra configuración.
4. Bloque 26: recuperación, contexto, citas, prompt y escenarios A/B/C.
5. Suite global, documentación, `git diff --check` y `git status --short`.

No se hará `git commit` ni `git push`.

## 7. Optimización del recuperador (Bloque 26) — motivo de una nueva indexación

Registrado **antes** de calcular nuevos embeddings (12 de noviembre de 2026).

- Diagnóstico sobre `corpus_proyecto_bloque24` (200/30): la evidencia del escenario B (`docs/limites_autonomia_agente.md`, línea 13) está indexada, pero el párrafo quedó dividido en 5 chunks (5–9). El encabezado `## Supervisión humana` quedó aislado (chunk 5), y la frase clave (chunk 7, ID `docs-limites-autonomia-agente-md:0007:2d2c9bfd96`) comienza con `". "` y ocupa la posición 28 de 273 (distancia 0,3384). No hay filtros de metadatos en la búsqueda.
- En todo el índice, 19 de los 21 chunks de menos de 40 caracteres son encabezados aislados y 52 de 273 chunks empiezan con `". "`.
- La búsqueda híbrida (BM25 + RRF) sobre ese índice **no mejora** Hit@3 (0,714 vectorial frente a 0,571 híbrida) y no recupera B: la causa raíz es la pérdida de contexto del chunking.
- Evaluación offline (sin costo) de la nueva estrategia `markdown`: 242 chunks, 0 encabezados aislados, 0 chunks que empiezan con `". "` y 0 cortes de palabra.
- Decisión: indexar el corpus con `--estrategia markdown` (200/30) en la colección **nueva** `corpus_proyecto_bloque24_md`. Costo estimado: 242 embeddings, unos 13 lotes (~3,5 min con la cuota gratuita). **No se reconstruye ni se borra** `corpus_proyecto_bloque24` ni ninguna otra colección; el índice del Bloque 24 se conserva como línea base.

## 8. Consolidación (12 de noviembre de 2026)

- **Modo predeterminado de la CLI:** índice `markdown` + búsqueda vectorial + expansión por sección. Justificación: mejor Hit@3 por evidencia en desarrollo (1,0 frente a 0,714 de la base) y en validación (1,0 frente a 0,833), sin llamadas adicionales a la API. Opciones explícitas: `--indice base`, `--sin-expandir`, `--modo hibrido`, `--max-contexto`.
- **BM25/RRF:** se mantiene como opción. No mejoró en este corpus por el vocabulario distinto, el ruido de términos frecuentes y porque RRF puede subir el error de un solo ranking (detalle en `README-bloque26.md`).
- **Evaluación:** el conjunto de desarrollo (7 + 2) queda congelado. El de validación (6 + 2) está separado, no se usó para ajustar el sistema y lo redactó el mismo autor. Ninguno demuestra generalización.
- **Costos de contexto:** entre 3,7 y 28,6 veces más caracteres de entrada por generación en los escenarios A–C. Se registran por consulta (`unidades_contexto`, `chunks_recuperados`, `secciones_expandidas`, `caracteres_contexto`, `fuentes_citadas`, `citas_invalidas`).
- **Actualización de documentos del corpus:** `--plan` (sin API) antes de indexar; `--podar-huerfanos` para eliminar solo los chunks obsoletos de la colección indicada. No se borran colecciones. La edición de `README.md` añadió 23 y 19 chunks sin dejar huérfanos.
