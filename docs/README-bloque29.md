# Bloque 29 — Dataset de personalización y preparación de tuning

## Objetivo

Preparar y validar un dataset propio para una tarea de **comportamiento consistente**: convertir un mensaje de error técnico del proyecto en un JSON con exactamente dos claves.

```json
{"categoria": "red", "accion_sugerida": "reintentar con backoff exponencial"}
```

El problema no es la falta de conocimiento documental (eso lo cubre el RAG de los Bloques 24–28), sino la consistencia de la clasificación y del formato. **En este bloque no se entrenó ningún modelo**: se prepararon y validaron los datos, y la configuración de tuning se construyó solo en local.

## Arquitectura

| Archivo | Responsabilidad |
|---|---|
| `src/personalizacion/dataset.py` | Categorías, claves, reglas de coherencia categoría ↔ acción, carga y conversión a `types.TuningExample` / `types.TuningDataset` |
| `src/personalizacion/validacion.py` | `validar_dataset` (todos los problemas en una sola pasada), `validar_salida`, `solapamiento` entre entrenamiento y validación |
| `src/personalizacion/balance.py` | `chequear_balance` con `collections.Counter` y `formatear_balance` |
| `src/personalizacion/configuracion_tuning.py` | `info_sdk`, `construir_config_peft`, `verificar_compatibilidad` (conversores locales del SDK) y `crear_trabajo_tuning` **bloqueado** |
| `src/personalizacion/evaluacion.py` | Checks deterministas offline sobre respuestas (JSON, claves exactas, categoría válida, coherencia y coincidencia) |
| `src/dataset_tuning.py` | CLI: `python -m src.dataset_tuning` |
| `data/personalizacion/ejemplos_entrenamiento.json` | 25 ejemplos |
| `data/personalizacion/ejemplos_validacion.json` | 10 ejemplos, separados del entrenamiento |

No se modificó ningún módulo de los Bloques 12–28. A `requirements.txt` solo se agregaron `google-genai==2.34.0` y `pydantic==2.14.2`, que ya estaban instalados como dependencias de `langchain-google-genai` y que ahora se importan directamente.

## Categorías: revisión frente al código

Se mantienen las cinco categorías propuestas, porque se corresponden con las clases de error y las políticas que el código ya distingue:

| Categoría | Errores del proyecto | Política verificada en el código |
|---|---|---|
| `red` | `ErrorTransitorio`, `TimeoutError`, `ConnectError`, `ReadTimeout`, 5xx | `con_reintento` (`src/cliente.py`) reintenta solo `TimeoutError` con backoff exponencial y jitter; `reintentos.py` clasifica 408/5xx y errores de red como transitorios |
| `autenticacion` | 400 `API_KEY_INVALID`, 401, 403, `CredencialesInvalidasError`, `CredencialesFaltantesError` | **Nunca** se reintentan (`CredencialesInvalidasError` no hereda de `TimeoutError`) |
| `cuota` | 429 `RESOURCE_EXHAUSTED` | El código lo reintenta igual que un fallo de red, pero la acción humana es distinta: bajar el ritmo (`--lote`, `--pausa` de `src.indexar_corpus`) o revisar el plan |
| `entorno` | `ModuleNotFoundError`, `DependenciaFaltanteError`, `DirectorioNoEscribibleError`, `PermissionError`, sqlite3 < 3.35.0 | Se corrige el entorno; reintentar no sirve |
| `consistencia_indice` | `EmbeddingsIncompatiblesError` (modelo o dimensión), `ConfiguracionIncompatibleError`, `ColeccionInexistenteError`, `IndiceVacioError`, `MetadataFaltanteError` | Indexar o reconstruir con `--reconstruir` |

Decisiones de frontera, documentadas para que el etiquetado sea consistente:

- **5xx va en `red`** y no en una categoría «servicio», porque el código aplica exactamente la misma política (backoff).
- **429 queda en `cuota`** aunque el código lo reintente como `red`: la acción sugerida cambia.
- **La clave ausente va en `autenticacion`**, no en `entorno`: la acción siempre trata sobre la credencial y nunca consiste en reintentar.
- El mensaje de `src/cliente.py` *«Gemini respondió HTTP {código}; error temporal o cuota excedida.»* es ambiguo: con 429 es `cuota` y con 502 es `red`. Se incluyeron ambos a propósito como par contrastivo.

## Dataset

- 25 ejemplos de entrenamiento + 10 de validación = **35**, escritos para este proyecto (no se copió el dataset del PDF). Las entradas reproducen mensajes reales del código (`src/rag/indexador.py`, `src/rag/configuracion.py`, `src/cliente.py`, agentes de los Bloques 21–23), de chromadb (chequeo de sqlite3) y del SDK.
- Formato de cada ejemplo: `{"entrada": str, "salida": str}`, donde `salida` es el JSON **serializado como texto**, igual que `TuningExample.output`.
- Casos cubiertos: timeout, fallo de conexión/DNS, API key inválida, 401, 403, clave ausente, 429 por minuto, 429 diario e indexación, dependencias faltantes, permisos de escritura, archivo bloqueado, sqlite3, modelo y dimensión de embeddings incompatibles, colección inexistente o vacía, chunking incompatible y metadata faltante.

### Distribución (salida real de `chequear_balance`)

| Categoría | Entrenamiento | Validación |
|---|---|---|
| red | 5 (20 %) | 2 (20 %) |
| autenticacion | 5 (20 %) | 2 (20 %) |
| cuota | 5 (20 %) | 2 (20 %) |
| entorno | 5 (20 %) | 2 (20 %) |
| consistencia_indice | 5 (20 %) | 2 (20 %) |

Relación máx/mín = 1,00 en ambos conjuntos. Mayoritaria y minoritaria: las cinco empatan. El umbral de 1,5 es una convención didáctica, no un requisito de la API. **Que el validador no informe errores no se usa como prueba de balance**: son dos comprobaciones separadas (hay un test que lo demuestra con un dataset válido de una sola categoría).

## Validación

`validar_dataset` revisa todos los ejemplos sin detenerse en el primer fallo y devuelve objetos `Problema(nivel, codigo, mensaje, indices)`:

- **Errores:** dataset que no es lista o está vacío; ejemplo que no es objeto; claves del ejemplo faltantes o inesperadas; entrada no textual o vacía; salida no textual o vacía; JSON malformado o que no es objeto; claves `categoria`/`accion_sugerida` faltantes o inesperadas; tipos incorrectos; categoría desconocida; acción vacía; contradicción categoría ↔ acción; registro idéntico; entrada duplicada (normalizada), señalando si las etiquetas se contradicen; fuga de validación a entrenamiento.
- **Advertencias:** entradas muy parecidas (`difflib`, similitud ≥ 0,85), validación parecida a entrenamiento y acción sin ningún término típico de su categoría.

Las contradicciones se detectan con reglas explícitas (`REGLAS_COHERENCIA`). Por ejemplo, en `autenticacion` está prohibido «reintentar» salvo en la forma negada «no reintentar», y en `entorno` está prohibido «backoff» o «cuota».

### Resultado real sobre el dataset final

```text
Entrenamiento (25 ejemplos): 0 errores, 0 advertencias
Validación (10 ejemplos): 0 errores, 0 advertencias
Solapamiento entrenamiento/validación: 0 errores, 2 advertencias
  validación 1 ~ entrenamiento 11 (similitud 0.97)   ← mismo mensaje de cliente.py con 502 (red) frente a 429 (cuota)
  validación 6 ~ entrenamiento 15 (similitud 0.88)   ← ModuleNotFoundError de langchain_chroma frente a chromadb
```

Ambas advertencias son pares contrastivos intencionales. Se conservaron, pero el primero hace que ese caso de validación sea más fácil de lo que sería con un mensaje nuevo.

## Evaluación offline

`evaluar_respuestas(referencias, respuestas, origen)` aplica checks deterministas. Sin respuestas de un modelo, el CLI ejecuta un **control de referencia** (las propias salidas esperadas), que da 100 % en todos los checks: eso solo verifica el evaluador y **no mide ningún modelo**. Para evaluar respuestas reales, por ejemplo de Gemini base:

```powershell
python -m src.dataset_tuning --respuestas ruta\respuestas.json --origen gemini_base
```

En este bloque no se generaron respuestas con Gemini (sin llamadas a la API).

## SDK google-genai 2.34.0 (introspección local)

Disponibles: `TuningExample`, `TuningDataset`, `TuningMode` (`TUNING_MODE_FULL`, `TUNING_MODE_PEFT_ADAPTER`), `AdapterSize` (`ONE`…`THIRTY_TWO`), `CreateTuningJobConfig`, `TuningValidationDataset`, `TuningMethod` y `client.tunings.tune(base_model, training_dataset, config)`.

`construir_config_peft()` crea `CreateTuningJobConfig(tuning_mode=TUNING_MODE_PEFT_ADAPTER, adapter_size=ADAPTER_SIZE_ONE)` y no fija `epoch_count` para no inventar hiperparámetros. Al pasar la configuración por los **conversores locales del propio SDK** (sin red), se obtuvo:

| Dataset + config PEFT | Modo Developer API (clave de API) | Modo Vertex |
|---|---|---|
| Ejemplos inline (`examples`) | Rechazada: `adapter_size` solo en Vertex | Rechazada: `examples` solo en Developer API |
| `gcs_uri` (marcador, no existe) | Rechazada: `gcs_uri` solo en Vertex | El SDK la aceptaría |

**Diferencia con el material académico:** construir un `TuningDataset` con ejemplos inline y una configuración PEFT con `adapter_size` en el mismo código no es enviable en ningún modo con este SDK. PEFT requiere Vertex y un dataset JSONL en Cloud Storage. Que el SDK acepte la petición **no** significa que la cuenta tenga acceso al servicio ni que el modelo admita tuning; nada de eso se verificó.

## Seguridad del entrenamiento

- Ningún módulo crea `genai.Client` ni hace llamadas de red al importarse (hay un test en un proceso aislado con sockets y `genai.Client` bloqueados).
- `crear_trabajo_tuning` exige a la vez: `autorizacion="AUTORIZO_TUNING_CON_COSTO"`, la variable `PERSONALIZACION_AUTORIZAR_TUNING` con la misma frase y un `base_model` incluido en `MODELOS_TUNING_VERIFICADOS`, que está **vacío**. Ningún CLI la invoca.
- No se inició ningún trabajo de tuning, no se consultaron trabajos y no se presupuso ningún costo.

## Pruebas

```powershell
python -m pytest tests/test_personalizacion_dataset.py tests/test_personalizacion_validacion.py -v
```

48 pruebas (18 + 30), todas offline: cantidad mínima, JSON y claves exactas, categorías, duplicados y fugas, balance, casos requeridos, autenticación sin reintentos, conversión a `TuningExample` real, configuración PEFT local, compatibilidad por modo, tuning prohibido por defecto (con cliente espía), importación sin red, dataset corrupto (en memoria y en `tmp_path`) con 14 tipos de error detectados en una sola pasada, CLI con código de salida 1 y evaluación offline con respuestas defectuosas.

## Limitaciones

- 35 ejemplos sirven para la actividad y para ejemplos few-shot, pero quedan lejos de un dataset de entrenamiento serio.
- Las reglas de coherencia son léxicas: detectan contradicciones evidentes, no acciones incorrectas redactadas de otra manera.
- La similitud con `difflib` es una heurística de caracteres, no semántica.
- No se midió el comportamiento de ningún modelo.

## Pendiente para un entrenamiento real

Ver `docs/decision_personalizacion.md`, sección 4: más ejemplos, revisión manual de 20, una muestra de respuestas del modelo base, un proyecto Vertex con bucket, la confirmación de qué modelo admite tuning, el presupuesto y la autorización explícita.
