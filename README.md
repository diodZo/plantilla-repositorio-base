# Miniaplicación Python — Google Gemini

Proyecto de la **Especialización en Desarrollo con IA Generativa**. Consume la API REST de Gemini, maneja fallos de solicitud y valida respuestas JSON estructuradas mediante un banco de prompts reutilizable. Además incluye un cliente modular con reintentos y estimación de costos, un pipeline de procesamiento de texto, métricas de evaluación léxica y una cadena de tres pasos con LangChain, desarrollados por bloques.

## Requisitos

- Python 3.10 o superior (el proyecto se verificó con Python 3.13.5).
- Git y conexión a internet.
- Una API Key de Gemini con cuota disponible y acceso al modelo configurado.

## Instalación desde cero

```powershell
git clone https://github.com/diodZo/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

En macOS/Linux sustituye la activación por `source .venv/bin/activate` y copia con `cp .env.example .env`. Si corresponde usa `python3` en vez de `python`.

`requirements.txt` incluye `python-dotenv`, `requests`, `pytest`, `langchain` y `langchain-google-genai`.

Edita `.env` (no `.env.example`) con tus valores privados:

```dotenv
API_KEY=tu_clave_privada_de_gemini
AI_MODEL=gemini-3.5-flash-lite
```

El identificador del modelo debe existir y estar habilitado para tu API Key. **Nunca compartas el archivo `.env`.** El archivo `.gitignore` lo excluye del control de versiones.

Para comprobar la configuración sin mostrar la clave:

```powershell
python -m src.variables_entorno
```

## Ejecutar la miniaplicación

Desde la raíz del repositorio y con el entorno virtual activado:

```powershell
python -m src.consumir_gemini
```

El módulo realiza una pregunta de demostración y muestra el texto generado. Si Gemini no responde, el programa muestra un error controlado. Se necesita cuota disponible para ejecutar la solicitud.

## Pruebas automatizadas

```powershell
python -m pytest tests/ -v
```

Las pruebas de `tests/` usan dobles de prueba (`unittest.mock`, `RunnableLambda`, `tmp_path`): **no llaman a Gemini, no consumen cuota y no escriben en `docs/`**.

## Módulos por bloque

Ejecutar siempre desde la raíz del repositorio.

| Bloque | Módulo | Comando | ¿Consume cuota? |
|---|---|---|---|
| 12–13 | `src/cliente.py`: reintentos con backoff exponencial y jitter, clasificación de errores y costo referencial | `python -m src.cliente` | Sí |
| 15 | `src/pipeline_texto.py`: limpieza, tokenización y coincidencia de palabras | `python -m src.pipeline_texto` | No |
| 15 | `src/ensayo_bloque15.py`: tres consultas reales | `python -m src.ensayo_bloque15` | Sí (sobrescribe `docs/ensayo-bloque15.md`) |
| 16 | `src/metricas_texto.py`: precisión, cobertura y F1 léxicos | `python -m src.metricas_texto` | No |
| 16 | `src/ensayo_bloque16.py`: 20 consultas reales, reanudable | `python -m src.ensayo_bloque16 --cantidad 20` | Sí (omite consultas ya registradas en `docs/resultados_metricas.json`) |
| 17 | `src/preparar_revision_bloque17.py`: selecciona 10 casos para revisión manual | `python -m src.preparar_revision_bloque17 --entrada docs/resultados_metricas.json` | No (**sobrescribe `docs/revision_manual_bloque17.json`**, que ya contiene la revisión manual) |
| 18 | `src/cadena_tres_pasos.py`: chain LangChain clasificar → redactar → revisar | `python -m src.cadena_tres_pasos` | Sí (tres llamadas) |

`src/utils/comparar_modelos_gemini.py` es el benchmark citado en el ADR: realiza 30 solicitudes y **sobrescribe `docs/comparacion_modelos.csv`**. Se conserva como evidencia metodológica.

## Banco de prompts y consistencia

El banco en `prompts/banco.py` contiene los casos `clasificar_sentimiento`, `extraer_entidades` y `resumen_corto`, con instrucciones de sistema, ejemplos y esquemas JSON.

```powershell
python -m prompts.test_consistencia --repeticiones 3 --espera 3 --reintentos 2
```

Este comando hace **al menos nueve intentos independientes** contra la API (puede hacer solicitudes adicionales cuando hay reintentos), consume cuota y crea o reemplaza `prompts/registro_resultados.json`. Verifica las claves y los tipos del JSON y conserva los errores de servicio separados de los de estructura. Si recibes un 429 de cuota agotada con una espera larga, detén nuevas ejecuciones hasta que se restablezca o utiliza un modelo habilitado con cuota.

`prompts/test_consistencia.py` no forma parte de la suite de pytest: es un script de ejecución real.

## Estructura principal

```text
src/consumir_gemini.py              Consumo HTTP de Gemini y manejo de errores (Gate 1)
src/variables_entorno.py            Comprobación segura de configuración
src/cliente.py                      Cliente modular con reintentos y costos (Bloques 12–13)
src/pipeline_texto.py               Limpieza y tokenización (Bloque 15)
src/ensayo_bloque15.py              Ensayo real del Bloque 15
src/metricas_texto.py               Precisión, cobertura y F1 (Bloque 16)
src/ensayo_bloque16.py              Generación de resultados reales (Bloques 16–17)
src/preparar_revision_bloque17.py   Muestra para revisión manual (Bloque 17)
src/cadena_tres_pasos.py            Chain de tres pasos con LangChain (Bloque 18)
src/utils/comparar_modelos_gemini.py Benchmark de modelos (ADR-001)
prompts/banco.py                    Tres prompts con esquema de respuesta
prompts/test_consistencia.py        Pruebas repetidas de JSON estructurado
prompts/registro_resultados.json    Evidencia de la ejecución real
tests/                              Pruebas pytest sin llamadas reales
docs/                               Evidencias, ADR y documentación por bloque
requirements.txt                    Dependencias Python
.env.example                        Variables de ejemplo sin secretos
```

**Nota:** `src/main.py` está vacío. Los puntos de entrada son los módulos indicados en las secciones anteriores.

## Documentación por bloque

| Bloque | Documentos |
|---|---|
| Gate 1 | [ensayo-gate1.md](docs/ensayo-gate1.md), [evidencia_peticion_autenticada.md](docs/evidencia_peticion_autenticada.md) |
| ADR | [decision-arquitectura.md](docs/decision-arquitectura.md), [diagrama_arquitectura.png](docs/diagrama_arquitectura.png), [comparacion_modelos.csv](docs/comparacion_modelos.csv) |
| 13 | [ensayo-bloque13.md](docs/ensayo-bloque13.md) |
| 14 | [ensayo-bloque14.md](docs/ensayo-bloque14.md) |
| 15 | [README-bloque15.md](docs/README-bloque15.md), [ensayo-bloque15.md](docs/ensayo-bloque15.md) |
| 16 | [README-bloque16.md](docs/README-bloque16.md), [resultados_metricas.json](docs/resultados_metricas.json) |
| 17 | [README-bloque17.md](docs/README-bloque17.md), [entrega-bloque17.md](docs/entrega-bloque17.md), [revision_manual_bloque17.json](docs/revision_manual_bloque17.json), [limites_metrica.md](docs/limites_metrica.md) |
| 18 | [README-bloque18.md](docs/README-bloque18.md), [ensayo-bloque18.md](docs/ensayo-bloque18.md) |

Auditoría del repositorio: [auditoria-repositorio.md](docs/auditoria-repositorio.md).

## Instalación limpia para Gate 1

Clona el repositorio en **otra carpeta**, crea allí un entorno virtual nuevo, instala únicamente desde `requirements.txt`, configura `.env` a partir de `.env.example` y ejecuta los comandos indicados arriba sin utilizar librerías previamente instaladas. Guarda el resultado real en `docs/ensayo-gate1.md`.

Comprueba también:

```powershell
git status --short
git ls-files .env
git log --all --oneline -- .env
```

Los dos últimos comandos no deberían mostrar ninguna entrada para el archivo `.env`. Si una clave real se filtró en algún commit, revócala/regenérala en Google AI Studio y evalúa limpiar el historial.

## Documentación de la decisión

Ver [diagrama de arquitectura](docs/diagrama_arquitectura.png), [registro de decisión de arquitectura](docs/decision-arquitectura.md) y [resultados comparativos](docs/comparacion_modelos.csv). El cálculo de costos del benchmark está documentado como medición independiente; no forma parte del flujo principal de `src/consumir_gemini.py`. El cliente modular `src/cliente.py` incorpora un costo **referencial** por tokens, con una tarifa ilustrativa que no corresponde al precio oficial de Gemini.

## RAG sobre la documentación del proyecto (Bloques 24–26)

Sistema de recuperación aumentada (RAG) que responde preguntas sobre la documentación del repositorio y cita sus fuentes. El código está en `src/rag/`; el detalle de cada bloque, en [README-bloque24.md](docs/README-bloque24.md), [README-bloque25.md](docs/README-bloque25.md), [README-bloque26.md](docs/README-bloque26.md) y [plan-rag-bloques24-26.md](docs/plan-rag-bloques24-26.md).

### Arquitectura

```text
corpus.py (8 documentos reales, metadata de origen)
  → chunking.py (recursivo o por secciones Markdown, IDs estables)
  → embeddings.py (models/gemini-embedding-001, reintentos solo para fallos transitorios)
  → indexador.py (Chroma persistente, indexación incremental sin duplicados)
  → recuperador.py / hibrido.py (vectorial; opcional BM25 + RRF)
  → expansion.py (cada chunk se reemplaza por su sección: small-to-big)
  → prompts.py (contexto numerado como datos, citas [n], abstención si falta información)
  → generador.py (Gemini, AI_MODEL de .env)
```

### Indexación y persistencia

Los índices se guardan en `vectorstore/` y `vectorstore_ejemplo/`, excluidos de Git. Las colecciones son `corpus_proyecto_bloque24` (recursivo 200/30), `corpus_proyecto_bloque24_md` (por secciones Markdown, 200/30, predeterminada para consultas) y `politicas_tienda_bloque25`. Volver a indexar solo calcula embeddings de los chunks nuevos. Ninguna colección se borra sin `--reconstruir`, y los chunks obsoletos solo se eliminan con `--podar-huerfanos`.

```powershell
python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md
python -m src.indexar_corpus --bloque 24 --plan --estrategia markdown --coleccion corpus_proyecto_bloque24_md
python -m src.indexar_corpus --bloque 24 --solo-verificar
python -m src.indexar_corpus --bloque 25
```

### Recuperación semántica y expansión

De forma predeterminada, `src/recuperar_corpus.py` usa el índice por secciones, búsqueda vectorial (distancia coseno; no es un porcentaje) y expansión de cada chunk a su sección. `--indice base --sin-expandir` reproduce el comportamiento original del Bloque 26; `--modo hibrido` agrega BM25 con Reciprocal Rank Fusion; `--max-contexto` limita el contexto sin recortar unidades.

```powershell
python -m src.recuperar_corpus "¿Qué herramienta requiere aprobación humana?"
python -m src.recuperar_corpus --escenarios
python -m src.recuperar_corpus "..." --sin-generar --k 5 --max-contexto 2500
python -m src.evaluar_recuperacion --indice markdown --expandir --conjunto validacion
```

Las consultas no recalculan embeddings de documentos: solo una `embed_query` por pregunta, y una generación si no se usa `--sin-generar`. Las pruebas de `tests/test_rag_*.py` usan embeddings simulados y no consumen cuota.

## Servicio RAG integrado (Gate 2)

**Objetivo.** Responder preguntas sobre la documentación del proyecto con fuentes citadas, de forma auditable y con defensas contra la inyección de prompt, integrando las Unidades 2.5 (RAG), 2.6 (personalización) y 2.7 (gobernanza). Detalle completo en [docs/README-gate2.md](docs/README-gate2.md); evidencias en [docs/entrega-gate2.md](docs/entrega-gate2.md).

**Arquitectura** (`src/servicio_rag.py` reutiliza los Bloques 24–32; no es una implementación paralela):

```text
consulta → trace_id → índice Chroma persistente → 1 embed_query → búsqueda → expansión small-to-big
→ filtro de inyección (unidades finales) → citas [1..n] reconstruidas → prompt system/human versionado
→ generación → validación de citas o abstención → respuesta JSON + auditoría JSONL + consumo
```

**Requisitos e instalación.** Python 3.10+ (verificado con 3.13.5) y `python -m pip install -r requirements.txt`. El modo demo **no necesita `.env`** ni clave de API.

| Tarea | Comando (PowerShell) |
|---|---|
| Verificar el entorno (sin llamar a Gemini) | `.\.venv\Scripts\python.exe -m src.preflight_gate2` |
| Consulta en modo DEMO (predeterminado, simulado) | `.\.venv\Scripts\python.exe -m src.servicio_rag` |
| Ensayo funcional completo (11 comprobaciones) | `.\.venv\Scripts\python.exe -m src.ensayo_gate2` |
| Autoevaluación con la rúbrica | `.\.venv\Scripts\python.exe -m src.rubrica_gate2` |
| Indexar el corpus real (incremental; usa Gemini) | `.\.venv\Scripts\python.exe -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md` |
| Consulta REAL (optativa, posible costo; preflight previo) | `.\.venv\Scripts\python.exe -m src.servicio_rag --real --pregunta "¿...?"` |
| Pruebas (sin red) | `.\.venv\Scripts\python.exe -m pytest tests/ -v` |

- **Modo DEMO:** corpus sintético, índice Chroma en un directorio temporal, embeddings y modelo simulados; las respuestas empiezan con `[SIMULADO]` y los tokens se marcan como `simulada`.
- **Modo REAL:** usa el índice existente (`vectorstore/`, ignorado por Git) sin reindexarlo. **No se ejecutó durante el Gate 2.**
- **Seguridad:** roles reales, contexto delimitado como no confiable, cuarentena de unidades con patrones de inyección después de la expansión, abstención si no queda contexto confiable y rechazo de respuestas con citas inexistentes o sin citas. No es una protección total: ver [docs/informe_seguridad_bloque31.md](docs/informe_seguridad_bloque31.md).
- **Observabilidad:** `logs/rag_auditoria.jsonl` (ignorado por Git) con un `trace_id` por consulta, tiempos, tokens, versión de prompt y estado final. No guarda preguntas, documentos, prompts ni credenciales.
- **Supervisión humana:** LangGraph con `interrupt` antes de activar una versión de prompt (`python -m src.grafo_supervision`). Sin autenticación de aprobadores; checkpointer en memoria.
- **Rutas heredadas no recomendadas:** `generador.responder`, `src.recuperar_corpus`, `src.registro_rag` y `src.evaluar_bloque27` omiten el filtro y la auditoría; se conservan por compatibilidad.
