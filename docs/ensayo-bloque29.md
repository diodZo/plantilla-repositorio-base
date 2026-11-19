# Ensayo Bloque 29 — Registro de la preparación del dataset

Fecha: 18 de noviembre de 2026 · Python 3.13.5 · Windows 11 · google-genai 2.34.0 · pydantic 2.14.2 · sin llamadas a la API.

## 1. Inspección

- `git status --short`: `?? "tatus --short"`. Es un archivo sin seguimiento cuyo contenido es la salida de un `git diff --stat` del Bloque 27 (probablemente un `git status --short` mal tecleado y redirigido). **No se modificó ni se borró**: decide el usuario.
- `src/cliente.py`: `enviar_peticion` convierte red, 429 y 5xx en `TimeoutError`, y 401/403 en `ValueError`. `con_reintento` solo reintenta `TimeoutError`, con backoff exponencial y jitter.
- `src/rag/reintentos.py`: `clasificar_error` devuelve `autenticacion` (401, 403 y 400 con `API_KEY_INVALID`), `transitorio` (408, 429, 5xx y errores de red) o `permanente`. `llamar_con_reintentos` usa 4 intentos.
- `src/rag/errores.py`: 13 clases. Se usaron como fuente de los mensajes de `entorno`, `autenticacion` y `consistencia_indice`.
- Chroma: `indexador.py` lanza `DependenciaFaltanteError`, `DirectorioNoEscribibleError`, `EmbeddingsIncompatiblesError`, `ConfiguracionIncompatibleError` y `ColeccionInexistenteError`; `recuperador.py` traduce `chromadb.errors.InvalidArgumentError` con «dimension» a `EmbeddingsIncompatiblesError`. Se comprobó en `chromadb/__init__.py` el texto real del error de sqlite3 (< 3.35.0). La versión local de sqlite3 es 3.49.1.
- Agentes de los Bloques 21–23: solo exigen la clave (`RuntimeError: Configura GOOGLE_API_KEY, GEMINI_API_KEY o API_KEY en .env`); ese mensaje se usó en validación.
- `.gitignore` excluye `.env`, `.venv/` y `vectorstore/`; `.env` existe y no se leyó. `requirements.txt` no declaraba `google-genai` ni `pydantic` (estaban instalados como dependencias de `langchain-google-genai 4.4.2`).
- `python` no está en el PATH del shell; se usó `.venv\Scripts\python.exe`.

## 2. SDK

```text
google-genai 2.34.0
TuningExample, TuningDataset, TuningMode, AdapterSize, CreateTuningJobConfig, TuningValidationDataset, TuningMethod: disponibles
AdapterSize: UNSPECIFIED, ONE, TWO, FOUR, EIGHT, SIXTEEN, THIRTY_TWO
TuningMode: UNSPECIFIED, FULL, PEFT_ADAPTER
Tunings.tune(*, base_model, training_dataset, config=None) -> TuningJob
```

Al leer el código de `google/genai/tunings.py` se encontró que `_CreateTuningJobConfig_to_mldev` lanza `ValueError` si recibe `adapter_size` o `tuning_mode`, y que `_TuningDataset_to_vertex` lo lanza si recibe `examples`. Se confirmó ejecutando esos conversores en local (resultados en el README). Es la diferencia principal con el material académico.

## 3. Ejecución del CLI

`python -m src.dataset_tuning` → código de salida 0.

- Entrenamiento: 25 ejemplos, 0 errores, 0 advertencias. Validación: 10 ejemplos, 0 errores, 0 advertencias.
- Solapamiento: 0 errores y 2 advertencias (similitud 0,97 y 0,88), ambas pares contrastivos intencionales.
- Balance: 5/5/5/5/5 y 2/2/2/2/2; relación máx/mín 1,00.
- Control de referencia del evaluador: 100 % en los cinco checks; incumplimiento de formato 0 % (no mide ningún modelo).
- `TuningDataset` local con 25 `TuningExample`; `CreateTuningJobConfig` con `TUNING_MODE_PEFT_ADAPTER` y `ADAPTER_SIZE_ONE`.
- Compatibilidad: inline + PEFT rechazada en ambos modos; `gcs_uri` + PEFT, aceptada solo en Vertex.
- «No se creó ningún trabajo de tuning ni se llamó a la API.»

## 4. El validador encuentra errores reales

Con el dataset corrupto de las pruebas (16 registros, generado en memoria y en `tmp_path`, nunca en `data/`), una sola ejecución devuelve los 14 códigos de error esperados: `entrada_vacia`, `salida_vacia`, `json_malformado`, `clave_faltante`, `clave_inesperada`, `categoria_desconocida`, `accion_vacia`, `tipo_entrada`, `contradiccion`, `registro_identico`, `entrada_duplicada` (con etiqueta contradictoria), `tipo_ejemplo`, `clave_ejemplo_faltante` y `clave_ejemplo_inesperada`. Además, devuelve la advertencia `entradas_muy_parecidas`. El CLI con ese archivo devuelve el código 1 y no construye objetos de tuning.

## 5. Pruebas

```text
tests/test_personalizacion_dataset.py     18 passed
tests/test_personalizacion_validacion.py  30 passed
```

## 6. Conclusión

El dataset está listo como material didáctico y como fuente de ejemplos few-shot. **No se entrenó ningún modelo**. La configuración PEFT del curso no puede enviarse tal como está con este SDK y con la credencial actual del proyecto, y la disponibilidad real de tuning en la cuenta no se verificó.
