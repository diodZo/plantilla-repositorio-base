# Auditoría del repositorio `plantilla-repositorio-base`

- **Fecha de la auditoría:** 2026-11-02
- **Directorio auditado:** `D:\Repositorios\curso\plantilla-base`
- **Rama:** `main`, sincronizada con `origin/main` en el commit `1752965`
- **Tipo de revisión:** no destructiva. Durante la auditoría solo se creó este archivo.

### Convenciones de clasificación

| Etiqueta | Significado |
|---|---|
| **REQUISITO DEL CURSO** | Respaldado por material académico disponible y verificable. |
| **IMPLEMENTACIÓN VERIFICADA** | Respaldada por archivos, código, pruebas, historial Git o comandos ejecutados. |
| **RECOMENDACIÓN TÉCNICA** | Buena práctica opcional, no exigida por el curso. |
| **NO VERIFICADO** | No se puede confirmar con las fuentes disponibles. |

> **Advertencia sobre el material académico.** El repositorio no contiene enunciados oficiales del curso. Los únicos textos con aspecto de instrucciones son los `README-bloqueNN.md` y algunas notas dentro de `docs/ensayo-*.md`, que se presentan como "paquetes" para integrar. Su origen, es decir, si son material oficial o instrucciones generadas durante el trabajo, **no se puede verificar**. Por eso este informe no clasifica ningún hallazgo como **REQUISITO DEL CURSO**. Cuando un documento menciona una exigencia de la actividad (por ejemplo, "20 respuestas"), se cita como **lo que dice el documento**, no como requisito confirmado.

---

## 1. Resumen ejecutivo

El repositorio está **funcional**: las 46 pruebas automatizadas pasan sin llamadas reales a Gemini, no hay credenciales expuestas en archivos versionados ni en el historial, y el código de los Bloques 12 a 18 está versionado en `origin/main`.

Hallazgos principales:

1. **ALTO — `README.md` sobrescrito.** La copia local reemplazó la documentación general del proyecto por una nota de 14 líneas titulada "Entrega Bloque 17". Si se hace commit, la documentación general desaparece de `main`.
2. **ALTO — `requirements.txt` incompleto.** No declara `langchain-core` ni `langchain-google-genai`, aunque `src/cadena_tres_pasos.py` y `tests/test_cadena_tres_pasos.py` los importan. Una instalación limpia no podría ejecutar el Bloque 18 ni sus pruebas.
3. **ALTO — La versión publicada de `tests/test_cliente.py` falla.** La versión de `HEAD` falla 2 de 3 pruebas con el `src/cliente.py` actual. **La modificación local corrige esta incoherencia** y conviene conservarla.
4. **MEDIO — Evidencia de Bloque 18 inconsistente.** `docs/ensayo-bloque18.md` contiene dos documentos concatenados: una plantilla que dice "pendiente" y un registro que declara "validación técnica satisfactoria".
5. **MEDIO — Evidencia sin versionar.** `src/utils/comparar_modelos_gemini.py` no está versionado, pero el ADR lo cita como la fuente del benchmark de `docs/comparacion_modelos.csv`. Además, si se ejecuta, **sobrescribe** ese CSV.
6. **MEDIO — Documentación por bloque dispersa y parcialmente sin versionar.** Afecta a los Bloques 15, 16 y 17. Los registros de los Bloques 13 y 14 siguen en estado "pendiente".

No se modificó código, no se ejecutaron `git add`, `commit`, `push`, `restore` ni `checkout`, y no se instalaron paquetes.

---

## 2. Alcance

Se revisó lo siguiente:

- **Código fuente:** `src/` completo, incluido el directorio no versionado `src/utils/`, y `prompts/`.
- **Pruebas:** `tests/` completo, más la versión de `HEAD` de `tests/test_cliente.py`, ejecutada en un directorio temporal fuera del proyecto.
- **Documentación:** `README.md` (copia local y `HEAD`), `README-bloque17.md` y `docs/` completo.
- **Configuración:** `.gitignore`, `requirements.txt`, `.env.example` y `.vscode/settings.json`. Del archivo `.env` solo se leyeron los **nombres** de las variables, no sus valores.
- **Entorno:** `.venv`, paquetes instalados y un segundo entorno virtual detectado, `ia.accenture.ven/`.
- **Historial Git:** 19 commits.

Fuera del alcance:

- La ejecución de módulos que consumen cuota: `src.consumir_gemini`, `src.cliente`, `src.ensayo_bloque15`, `src.ensayo_bloque16`, `src.cadena_tres_pasos`, `prompts.test_consistencia` y `src/utils/comparar_modelos_gemini.py`.
- La validación de una instalación limpia en otra carpeta, porque requiere instalar paquetes.

---

## 3. Fuentes de evidencia

Comandos ejecutados, todos de solo lectura salvo los indicados:

```powershell
Get-Location
git status --short ; git status --ignored --short
git branch -vv ; git remote -v ; git log --oneline
git diff --stat ; git diff --cached --stat
git diff -- README.md ; git show HEAD:README.md
git diff -- tests/test_cliente.py
git ls-files ; git ls-files --others --exclude-standard ; git ls-files --eol
git show --stat 1752965 5573437 6d863de
git show 5573437 -- requirements.txt
git log --all --oneline -- .env ; git ls-files .env
git grep (patrones de clave API, sin imprimir valores)
git config core.autocrlf
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest --version
.\.venv\Scripts\python.exe -m pip list
.\.venv\Scripts\python.exe -m pytest tests/ -v -p no:cacheprovider   # PYTHONDONTWRITEBYTECODE=1
.\.venv\Scripts\python.exe -m pytest <scratchpad>\test_cliente_head.py   # versión HEAD, fuera del repo
```

También se leyeron directamente todos los archivos `.py` de `src/`, `tests/` y `src/utils/`, y todos los `.md` de la raíz y de `docs/`.

---

## 4. Estado Git

**IMPLEMENTACIÓN VERIFICADA**

| Elemento | Valor |
|---|---|
| Rama | `main` → `origin/main`, sin commits adelantados ni atrasados |
| Remoto | `https://github.com/diodZo/plantilla-repositorio-base.git` |
| Último commit | `1752965` Versiona implementaciones de los Bloques 16 y 17 (2026-11-02 20:08 -0300) |
| Área de preparación | Vacía |

El estado observado coincide con el informado previamente:

```text
 M README.md
 M tests/test_cliente.py
?? README-bloque17.md
?? docs/README-bloque15.md
?? docs/README-bloque16.md
?? src/utils/                (contiene comparar_modelos_gemini.py y __pycache__/, ignorado)
```

Commits relevantes por bloque:

| Commit | Mensaje | Archivos |
|---|---|---|
| `6cdb933` | Agrega cliente modular con reintentos y pruebas | `src/cliente.py`, `tests/test_cliente.py` |
| `e43f4d3` | Implementa backoff exponencial y registro de costos | Bloque 13 |
| `b0922da` | Documenta resultados de pruebas unitarias del Bloque 14 | `docs/ensayo-bloque14.md` |
| `e56bc81` | Agrega pipeline de limpieza y tokenización del Bloque 15 | Bloque 15 |
| `6d863de` | Documenta revision cualitativa y limites del Bloque 17 | `docs/limites_metrica.md`, `docs/resultados_metricas.json`, `docs/revision_manual_bloque17.json` |
| `5573437` | Implementa chain de tres pasos con LangChain - Bloque 18 | `src/cadena_tres_pasos.py`, sus pruebas, docs y `requirements.txt` (+`pytest`) |
| `1752965` | Versiona implementaciones de los Bloques 16 y 17 | `src/metricas_texto.py`, `src/ensayo_bloque16.py`, `src/preparar_revision_bloque17.py`, `tests/test_metricas_texto.py` |

Observación: los datos del Bloque 17 (`6d863de`) se versionaron antes que el código que los genera (`1752965`). No es un error, pero explica por qué `docs/README-bloque16.md` no quedó incluido en ningún commit.

---

## 5. Inventario del proyecto

**IMPLEMENTACIÓN VERIFICADA.** La asociación a bloques sale de docstrings, mensajes de commit o documentos del propio repositorio.

### 5.1 Código fuente

| Ruta | Responsabilidad | Bloque | Estado Git | Dependencias | Riesgos |
|---|---|---|---|---|---|
| `src/consumir_gemini.py` | Cliente HTTP original: arma la petición, la envía, extrae el texto y maneja errores con `RuntimeError` | Gate 1 | Versionado | `requests`, `dotenv` | Consume cuota al ejecutarse con `__main__` |
| `src/variables_entorno.py` | Comprueba que existan `API_KEY` y `AI_MODEL` sin revelar su valor | Gate 1 | Versionado | `dotenv` | — |
| `src/main.py` | Vacío (0 líneas) | — | Versionado | — | El README de `HEAD` lo documenta como vacío |
| `src/cliente.py` | Cliente modular: clasifica errores (`ValueError` permanente, `TimeoutError` recuperable), aplica backoff con jitter y registra costo referencial | 12–13 | Versionado | `requests`, `src.consumir_gemini` | Estado global `costo_total_sesion` |
| `src/pipeline_texto.py` | Limpieza, tokenización, `Counter` y coincidencia de palabras | 15 | Versionado | stdlib | — |
| `src/ensayo_bloque15.py` | 3 consultas reales; escribe `docs/ensayo-bloque15.md` | 15 | Versionado | `src.cliente` | **Sobrescribe evidencia** y consume cuota |
| `src/metricas_texto.py` | Precisión, cobertura y F1 léxicos | 16 | Versionado | `src.pipeline_texto` | — |
| `src/ensayo_bloque16.py` | 20 consultas reales con reanudación; escribe `docs/resultados_metricas.json` | 16 | Versionado | `src.cliente`, `src.metricas_texto` | Consume cuota. No duplica: omite consultas ya registradas |
| `src/preparar_revision_bloque17.py` | Selecciona 5 F1 mínimos y 5 máximos; escribe `docs/revision_manual_bloque17.json` con la rúbrica en "pendiente" | 17 | Versionado | stdlib | **Reejecutarlo sobrescribe la revisión manual ya completada** |
| `src/cadena_tres_pasos.py` | Chain LangChain de tres pasos: clasificar, redactar y revisar | 18 | Versionado | `langchain_core`, `langchain_google_genai`, `dotenv` | Dependencias no declaradas en `requirements.txt` |
| `src/utils/comparar_modelos_gemini.py` | Benchmark de 2 modelos × 3 preguntas × 5 rondas; escribe `docs/comparacion_modelos.csv` | ADR / Bloque 8 según el ADR | **No versionado** | `requests`, `dotenv` | **Sobrescribe evidencia versionada** y hace 30 solicitudes |
| `prompts/banco.py` | Tres prompts con esquema JSON | Gate 1 | Versionado | — | — |
| `prompts/test_consistencia.py` | Script de consistencia contra la API real. **No es una prueba pytest**: pytest no lo recoge porque solo se ejecuta `tests/` | Gate 1 | Versionado | `src.consumir_gemini` | Consume cuota y reemplaza `prompts/registro_resultados.json` |

### 5.2 Pruebas

| Ruta | Pruebas | Bloque | Estado Git |
|---|---|---|---|
| `tests/test_cliente.py` | 18 (copia local) / 3 (`HEAD`) | 14 según su docstring local | **Modificado** |
| `tests/test_cliente_bloque13.py` | 5 (unittest) | 13 | Versionado |
| `tests/test_pipeline_texto.py` | 9 | 15 | Versionado |
| `tests/test_metricas_texto.py` | 11 | 16 | Versionado |
| `tests/test_cadena_tres_pasos.py` | 3 | 18 | Versionado |

### 5.3 Documentación y evidencias

| Ruta | Contenido | Estado Git |
|---|---|---|
| `README.md` | Ver la sección 6 | **Modificado** |
| `README-bloque17.md` | Instrucciones de integración del Bloque 17 ("plantilla de trabajo") | **No versionado** |
| `docs/README-bloque15.md` | Instrucciones del paquete del Bloque 15 | **No versionado** |
| `docs/README-bloque16.md` | Instrucciones del paquete del Bloque 16 | **No versionado** |
| `docs/README-bloque18.md` | Instrucciones del Bloque 18 | Versionado |
| `docs/ensayo-gate1.md` | Registro de la instalación limpia (9/9 intentos) | Versionado |
| `docs/evidencia_peticion_autenticada.md` | Respuesta JSON de la primera petición autenticada | Versionado |
| `docs/diagrama_arquitectura.png`, `docs/decision-arquitectura.md`, `docs/comparacion_modelos.csv` | Diagrama, ADR-001 y benchmark (30 filas de datos) | Versionado |
| `docs/ensayo-bloque13.md` | Plantilla, **todos los campos en "pendiente"** | Versionado |
| `docs/ensayo-bloque14.md` | Plantilla, **todos los campos en "pendiente"** | Versionado |
| `docs/ensayo-bloque15.md` | Resultados reales del 2026-10-29 | Versionado |
| `docs/resultados_metricas.json` | 20 registros con `consulta`, `referencia`, `respuesta`, `precision`, `cobertura`, `f1` y `fecha_utc` | Versionado |
| `docs/revision_manual_bloque17.json` | 10 casos con la rúbrica completada y nota en todos | Versionado |
| `docs/limites_metrica.md` | Análisis de los límites de la métrica (Bloque 17) | Versionado |
| `docs/ensayo-bloque18.md` | **Plantilla "pendiente" y registro "satisfactorio" concatenados** | Versionado |

### 5.4 Configuración y entorno

| Ruta | Observación | Estado |
|---|---|---|
| `.venv/` | Python 3.13.5 y pytest 9.2.0 | Ignorado |
| `ia.accenture.ven/` | **Segundo entorno virtual** (Python 3.13.5), creado el 2026-10-08. Se ignora mediante su propio `.gitignore` interno (`*`) | Ignorado |
| `.vscode/settings.json` | Apunta a `.venv\Scripts\python.exe` | Ignorado |
| `.env` | Contiene las variables `API_KEY` y `AI_MODEL` (valores no leídos) | Ignorado |

---

## 6. Auditoría de `README.md`

**IMPLEMENTACIÓN VERIFICADA.** Diff: 4 líneas añadidas y 81 eliminadas, con 10 líneas de contexto comunes.

**Contenido eliminado.** Es el README general del proyecto: descripción, requisitos, instalación desde cero, configuración de `.env`, ejecución de `src.consumir_gemini`, banco de prompts, estructura de carpetas, instalación limpia del Gate 1, verificación de que `.env` no está en el historial y enlaces al diagrama, al ADR y al CSV.

**Contenido agregado.** Una nota "Entrega Bloque 17" que indica:

- dos archivos (`docs/revision_manual_bloque17.json` y `docs/limites_metrica.md`);
- la instrucción "Copia los archivos dentro de la carpeta `docs/`…";
- el comando de commit con el mensaje *"Documenta revision cualitativa y limites del Bloque 17"*.

**Evaluación:**

- **Sobrescritura accidental: PROBABLE.** El nuevo texto está redactado como instrucciones de un paquete descargado ("Copia los archivos…") y no como documentación del proyecto. El commit que describe ya existe (`6d863de`, con el mismo mensaje). Que la sobrescritura haya sido accidental es una inferencia y queda como **NO VERIFICADO**.
- **Pertenencia:** el contenido corresponde al Bloque 17.
- **Contenido único:** el texto de la nota **no está duplicado** en ningún otro archivo. `README-bloque17.md` es un documento **distinto**: instrucciones de integración con 8 pasos.
- **Riesgo:** si se ejecuta `git add README.md` (o `git add .`), `main` pierde la documentación general. **Severidad: ALTO.**

**Propuesta de conservación:**

1. Preservar la nota local en `docs/` con un nombre propio (por ejemplo, `docs/entrega-bloque17.md`).
2. Recuperar `README.md` desde `HEAD`.

Comandos en la sección 14, acciones A2 y A3.

**Observación adicional sobre el README de `HEAD`** (**RECOMENDACIÓN TÉCNICA**, severidad MEDIO). Aunque se recupere, el README general está desactualizado: solo cubre hasta el Gate 1.

- Usa `python -m venv venv`, mientras que el entorno real del proyecto es `.venv`. Ambos están en `.gitignore`.
- La sección "Estructura principal" no menciona `src/cliente.py`, `pipeline_texto`, `metricas_texto`, `cadena_tres_pasos`, `tests/` ni los documentos de los Bloques 13 a 18.
- No documenta `python -m pytest tests/ -v`.
- Los enlaces que contiene (`docs/diagrama_arquitectura.png`, `docs/decision-arquitectura.md` y `docs/comparacion_modelos.csv`) **existen**: no hay enlaces rotos.

---

## 7. Auditoría de `tests/test_cliente.py`

**IMPLEMENTACIÓN VERIFICADA**

**Versión `HEAD`** (commit `6cdb933`). Tiene 3 pruebas con `unittest`:

- `test_reintento_exitoso`: simula `RuntimeError("…503")` y espera que `con_reintento` reintente.
- `test_no_reintentar_credencial`
- `test_reintentos_agotados`: espera un `RuntimeError` con el texto "tras varios intentos" desde `con_reintento`.

**Ejecución de la versión `HEAD` contra el `src/cliente.py` actual.** Se ejecutó en un directorio temporal fuera del repositorio. **Resultado: 2 fallan y 1 pasa.**

- `test_reintento_exitoso` **FALLA**: el `con_reintento` actual solo reintenta `TimeoutError` (`src/cliente.py:51`), así que el `RuntimeError` se propaga en el primer intento.
- `test_reintentos_agotados` **FALLA**: el mensaje "tras varios intentos" lo produce `consultar_modelo` (`src/cliente.py:79`), no `con_reintento`.
- Clasificación: **FALLO DE PRUEBA**. Las pruebas reflejan un contrato anterior de `con_reintento` que cambió con el backoff del commit `e43f4d3`.
- Consecuencia: **el `main` publicado en GitHub tiene hoy una suite con 2 pruebas fallidas.**

**Versión local** (no versionada). Tiene 18 pruebas pytest, con un docstring que dice *"Bloque 14: pruebas del cliente Gemini sin llamadas reales a la API"*. Cubre:

- `enviar_peticion`: 401/403 → `ValueError`; 429/500/502/503 → `TimeoutError`; éxito con `timeout=30`; `Timeout` y `ConnectionError` → `TimeoutError`.
- `con_reintento`: backoff `[2, 4]` con jitter anulado; no reintenta credenciales; propaga el mismo `TimeoutError` al agotar los intentos.
- `registrar_costo`: cálculo, acumulación y ausencia de metadatos.
- `consultar_modelo`: convierte `TimeoutError` en `RuntimeError("…tras varios intentos…")`; propaga `ValueError`; registra el costo una sola vez; agrega `systemInstruction`.

**Evaluación:**

| Criterio | Resultado |
|---|---|
| ¿Las funciones probadas existen en `src/cliente.py`? | Sí: `enviar_peticion`, `con_reintento`, `registrar_costo`, `consultar_modelo`, `COSTO_POR_1000_TOKENS` y `costo_total_sesion` |
| ¿Llama a la red? | No: `requests.post`, `time.sleep`, `random.uniform`, `armar_peticion` y `con_reintento` están parcheados |
| ¿Aísla el estado global? | Sí, con una fixture `autouse` que reinicia `costo_total_sesion` |
| ¿Código de depuración? | No se detectó |
| ¿Solapa con otras pruebas? | Sí, parcialmente con `tests/test_cliente_bloque13.py` (backoff, credencial, costo, 429, 401). Es razonable si cada archivo representa la evidencia de un bloque distinto (13 frente a 14) |
| Estilo menor | Usa `__import__("requests")` en `parametrize` en vez de un `import requests` normal. Funciona, pero es poco idiomático (BAJO) |

**Conclusión:** la modificación es una **corrección válida y una ampliación** de las pruebas. **Recomendación: conservarla y versionarla.** Se pierden las 3 pruebas `unittest` originales, pero 2 de ellas ya no son compatibles con el código, y la tercera (credencial) está cubierta por `test_con_reintento_no_reintenta_credencial`. Si se quiere preservar la trazabilidad, el historial Git ya conserva la versión original en `6cdb933`.

---

## 8. Auditoría de `src/utils/`

**IMPLEMENTACIÓN VERIFICADA**

**Contenido:**

- `comparar_modelos_gemini.py` (125 líneas, finales de línea CRLF).
- `__pycache__/comparar_modelos_gemini.cpython-313.pyc` (ignorado).
- No hay `__init__.py`. Funciona como script independiente o como paquete de espacio de nombres.

**Funciones:**

- `medir(modelo, pregunta, sesion)` hace un POST a Gemini, mide la latencia y calcula el costo con tarifas de entrada y salida, incluidos los `thoughtsTokenCount`.
- `ejecutar()` hace 30 solicitudes y escribe `docs/comparacion_modelos.csv`.

**Dependencias:** `requests` y `python-dotenv`, ambas declaradas en `requirements.txt`.

**Archivos sensibles:** no contiene secretos. Lee `API_KEY` desde `.env` en tiempo de ejecución.

**Importaciones:** ningún módulo del proyecto lo importa.

**Referencias:** `docs/decision-arquitectura.md` (líneas 31 y 37) lo cita como la herramienta que generó el benchmark del ADR, con la ruta **`utils/comparar_modelos_gemini.py`**. La ruta real es **`src/utils/comparar_modelos_gemini.py`**, así que la referencia no coincide.

**Coherencia con la evidencia:**

- El `.pyc` tiene fecha 2026-10-20 20:01 (hora local). La primera fila del CSV es 2026-10-20T23:01:49 UTC, es decir, 20:01 hora de Chile continental. Esto es compatible con que este script generara el CSV.
- El `.py` tiene fecha 20:02, posterior al `.pyc`. Es posible que se editara después de la última ejecución. **NO VERIFICADO** si la lógica cambió.

**Código duplicado:** reimplementa la llamada HTTP en lugar de reutilizar `src.consumir_gemini`. Es aceptable para un script de medición independiente, porque necesita `usageMetadata` y la latencia.

**Riesgo (MEDIO):** ejecutarlo **sobrescribe `docs/comparacion_modelos.csv`**, que es la evidencia versionada del ADR, y hace 30 solicitudes facturables.

**Recomendación:** **versionarlo** porque es la evidencia metodológica del ADR, y **no ejecutarlo**. Como **RECOMENDACIÓN TÉCNICA** opcional, más adelante se le puede agregar un parámetro de salida para no sobrescribir el CSV por defecto. Esa modificación necesita autorización aparte.

---

## 9. Documentación pendiente

**IMPLEMENTACIÓN VERIFICADA**

| Archivo | Objetivo | ¿Duplicado? | Contenido único | Propuesta |
|---|---|---|---|---|
| `README-bloque17.md` (raíz) | 8 pasos para integrar y validar el Bloque 17 | No. Es distinto de la nota del `README.md` local | Pasos de validación (20+ respuestas, 10+ revisiones, 4 secciones) y la aclaración "plantilla, no evidencia" | **Reubicar** a `docs/README-bloque17.md`, igual que los Bloques 15, 16 y 18, y versionar |
| `docs/README-bloque15.md` | Ubicación de archivos y pasos del Bloque 15 | No | Comandos de verificación del Bloque 15 | **Conservar y versionar** |
| `docs/README-bloque16.md` | Instalación, verificación y ensayo real del Bloque 16 | No | Explica la reanudación, el formato del JSON y la advertencia de privacidad | **Conservar y versionar** |
| Nota "Entrega Bloque 17" (hoy en `README.md`) | Lista de archivos del Bloque 17 | No | Comando de commit y referencia a `resultados_metricas.json` | **Preservar** en `docs/entrega-bloque17.md` (sección 6) |

Comprobación de rutas y comandos documentados:

- Todos los módulos citados en `README-bloque15.md`, `README-bloque16.md` y `README-bloque17.md` existen: `src/pipeline_texto.py`, `src/ensayo_bloque15.py`, `src/metricas_texto.py`, `src/ensayo_bloque16.py`, `src/preparar_revision_bloque17.py` y sus pruebas.
- `README-bloque16.md` afirma que "`requirements.txt` no cambia". Para el Bloque 16 es correcto, porque solo usa la biblioteca estándar.
- `README-bloque17.md`, paso 8, usa `&&` para encadenar comandos. **Windows PowerShell 5.1 no lo admite**; PowerShell 7 sí. El comando funcionaría solo en PowerShell 7 o en bash (BAJO).
- `README-bloque17.md`, paso 4, indica ejecutar `preparar_revision_bloque17`. **Reejecutarlo hoy sobrescribiría `docs/revision_manual_bloque17.json`**, que ya tiene la rúbrica completa. Conviene anotar esta advertencia al versionarlo (MEDIO).
- Estos documentos están redactados como instrucciones de "paquete" ("Copia `src/`…", "Este paquete…"). Se conservan como están porque forman parte del registro del trabajo. No se reescriben.

### 9.1 Documentación por bloque (12–18)

| Bloque | Código | Pruebas | Instrucciones | Evidencia | Observación |
|---|---|---|---|---|---|
| 12 | `src/cliente.py` (commit `6cdb933`) | `tests/test_cliente.py` | — | — | **No se encontró** un documento específico del Bloque 12 |
| 13 | `src/cliente.py` (`e43f4d3`) | `tests/test_cliente_bloque13.py` | Dentro de `docs/ensayo-bloque13.md` | `docs/ensayo-bloque13.md`: **todo "pendiente"** | Falta el registro real de backoff, 429 y costo. **No debe rellenarse sin una ejecución real** |
| 14 | — | `tests/test_cliente.py` (local) | Dentro de `docs/ensayo-bloque14.md` | `docs/ensayo-bloque14.md`: **todo "pendiente"** | Puede completarse con una ejecución real de pytest. Esta auditoría obtuvo 46 aprobadas en 0,76 s, pero **el autor debe registrar su propia ejecución** sobre el commit que finalmente pruebe |
| 15 | `pipeline_texto.py`, `ensayo_bloque15.py` | `test_pipeline_texto.py` | `docs/README-bloque15.md` (**no versionado**) | `docs/ensayo-bloque15.md` (real, 2026-10-29) | Completo salvo el versionado del README |
| 16 | `metricas_texto.py`, `ensayo_bloque16.py` | `test_metricas_texto.py` | `docs/README-bloque16.md` (**no versionado**) | `docs/resultados_metricas.json` (20 registros) | Completo salvo el versionado del README |
| 17 | `preparar_revision_bloque17.py` | Ninguna prueba directa | `README-bloque17.md` (**no versionado, en la raíz**) | `revision_manual_bloque17.json` (10 casos completos) y `limites_metrica.md` | Evidencia completa. `seleccionar_muestra` no tiene pruebas (BAJO) |
| 18 | `cadena_tres_pasos.py` | `test_cadena_tres_pasos.py` | `docs/README-bloque18.md` | `docs/ensayo-bloque18.md` | **Documento con plantilla y registro concatenados** (ver abajo) |

**`docs/ensayo-bloque18.md`** (MEDIO, IMPLEMENTACIÓN VERIFICADA):

- Las líneas 1–13 dicen *"Estado: pendiente de ejecución real y revisión"*, con campos vacíos.
- La línea 14 empieza un segundo documento, sin línea en blanco de separación, que termina con *"Estado: validación técnica satisfactoria"*.
- El registro describe la respuesta de Gemini en prosa, pero **no incluye la salida textual ni la fecha de ejecución**.
- Que la ejecución real ocurriera queda como **NO VERIFICADO** con las fuentes disponibles: no se ejecutó en esta auditoría porque consume cuota.
- Propuesta: el autor decide si elimina la plantilla de las líneas 1–13 y si agrega la fecha y la salida real que conserve. **No se debe inventar la salida.**

---

## 10. Pruebas automatizadas

### Inspección previa

**IMPLEMENTACIÓN VERIFICADA**

- No hay `conftest.py`, `pytest.ini`, `pyproject.toml` ni `setup.cfg`. pytest se ejecuta con la configuración por defecto, desde la raíz.
- Ninguna prueba llama a Gemini:
  - `test_cliente*.py` parchean `requests.post` y `time.sleep`.
  - `test_cadena_tres_pasos.py` usa `RunnableLambda` como modelo falso.
  - `test_metricas_texto.py` usa `tmp_path` y `monkeypatch` para evitar la API.
- Ninguna escribe en `docs/`: la persistencia se prueba con `tmp_path`.
- Las importaciones de módulos solo ejecutan `load_dotenv()`, que lee `.env` sin hacer peticiones de red.
- `prompts/test_consistencia.py` **sí** consume cuota, pero no está dentro de `tests/` y pytest no lo recoge.

### Ejecución

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
.\.venv\Scripts\python.exe -m pytest tests/ -v -p no:cacheprovider --durations=5
```

| Métrica | Resultado |
|---|---|
| Plataforma | win32, Python 3.13.5, pytest 9.2.0, pluggy 1.7.0 |
| Plugins | `anyio-4.16.0`, `langsmith-0.14.17` (instalados como dependencias de LangChain) |
| Descubiertas | **46** |
| Aprobadas | **46** |
| Fallidas / omitidas / errores | 0 / 0 / 0 |
| Warnings | Ninguno informado |
| Duración | **0,76 s** |

Desglose: `test_cadena_tres_pasos.py` 3, `test_cliente.py` (local) 18, `test_cliente_bloque13.py` 5, `test_metricas_texto.py` 11 y `test_pipeline_texto.py` 9.

Ejecución adicional de la versión `HEAD` de `tests/test_cliente.py` (sección 7): **2 fallidas y 1 aprobada**. Clasificación: **FALLO DE PRUEBA**.

**Limitación:** el resultado corresponde al `.venv` local, que tiene LangChain instalado. **NO VERIFICADO** en una instalación limpia desde `requirements.txt`. Por inspección, `tests/test_cadena_tres_pasos.py` fallaría en la recolección con `ModuleNotFoundError: langchain_core` (sección 11). Sería un **FALLO DE ENTORNO** previsible.

---

## 11. Dependencias

**IMPLEMENTACIÓN VERIFICADA**

`requirements.txt` declara:

```text
python-dotenv==1.2.4
requests==2.34.2
pytest>=8.0,<10.0
```

| Paquete importado | Dónde | ¿Declarado? | Versión instalada en `.venv` |
|---|---|---|---|
| `requests` | `consumir_gemini`, `cliente`, `utils/comparar_modelos_gemini` | Sí (`==2.34.2`) | 2.34.2 |
| `dotenv` | Varios módulos | Sí (`==1.2.4`) | 1.2.4 |
| `pytest` | `tests/` | Sí (rango `>=8.0,<10.0`, sin fijar) | 9.2.0 |
| `langchain_core` | `src/cadena_tres_pasos.py`, `tests/test_cadena_tres_pasos.py` | **No** | `langchain-core` 1.7.4 |
| `langchain_google_genai` | `src/cadena_tres_pasos.py` | **No** | `langchain-google-genai` 4.4.2 |

Otros paquetes instalados que el código no importa directamente: `langchain` 1.4.8, `google-genai` 2.34.0, `google-auth` 2.62.0 y `pydantic` 2.14.2. Probablemente son dependencias transitivas o instalaciones del Bloque 18; `docs/README-bloque18.md` indica `pip install langchain langchain-google-genai`.

**Hallazgo (ALTO): faltan dependencias de LangChain.**

- `docs/README-bloque18.md` indica explícitamente: *"Agrega `langchain` y `langchain-google-genai` a tu `requirements.txt`… fija las versiones realmente instaladas"*.
- El commit `5573437`, *"Implementa chain de tres pasos con LangChain"*, modificó `requirements.txt`, pero **solo agregó `pytest`**. LangChain no se agregó.
- Impacto: una instalación limpia según el Gate 1 no podría ejecutar `src/cadena_tres_pasos.py` ni recolectar `tests/test_cadena_tres_pasos.py`.
- Recomendación: agregar las versiones **realmente instaladas y verificadas** en `.venv`, que son las mismas con las que se obtuvieron las 46 aprobadas:

  ```text
  langchain==1.4.8
  langchain-google-genai==4.4.2
  ```

  `langchain-core` llega como dependencia de ambos. Fijarlo es opcional. Si se fija, debe ser `langchain-core==1.7.4`.
- Riesgo de aplicarla: bajo. Se recomienda validarla con una instalación limpia en otra carpeta antes de darla por cerrada.

**RECOMENDACIÓN TÉCNICA (BAJO).** `pytest` se declara con un rango y no fijo, a diferencia del resto. Es aceptable, pero si se busca reproducibilidad exacta se puede fijar `pytest==9.2.0`. No se recomienda actualizar ningún paquete.

---

## 12. Seguridad

**IMPLEMENTACIÓN VERIFICADA.** No se imprimió ningún valor secreto.

| Verificación | Resultado |
|---|---|
| `git ls-files .env` | Sin salida: `.env` no está versionado |
| `git log --all --oneline -- .env` | Sin salida: `.env` nunca se versionó |
| `.gitignore` cubre `.env`, `.venv/`, `venv/`, `__pycache__/` y `*.py[cod]` | **Sí** |
| `.gitignore` cubre `.pytest_cache/` | No de forma explícita, pero pytest crea su propio `.gitignore` interno y `git status --ignored` lo muestra como ignorado. **Sin riesgo actual** |
| Patrón de clave Google (`AIza…`) en archivos versionados | 0 coincidencias |
| El mismo patrón en todo el historial (`git log --all -p`) | 0 coincidencias |
| El mismo patrón en archivos no versionados | 0 coincidencias |
| `.env.example` | Solo contiene marcadores (`coloca_aqui_tu_clave_real`) |
| `docs/evidencia_peticion_autenticada.md` | Contiene `thoughtSignature`, una firma opaca de la respuesta del modelo. **No es una credencial** |

**No se detectaron credenciales comprometidas.** No hay recomendación de rotación.

Riesgos menores:

- **BAJO — Segundo entorno virtual `ia.accenture.ven/` dentro del repositorio.** Está ignorado y no hay riesgo de que se suba, pero genera confusión con `.venv`. Su eliminación queda a decisión del usuario.
- **BAJO — Respuestas del modelo en un repositorio público.** `docs/resultados_metricas.json` y los ensayos guardan respuestas del modelo. Su contenido son conceptos de Python sin datos personales, así que no hay un riesgo concreto. `README-bloque16.md` ya advierte sobre esto.

### Finales de línea (LF/CRLF)

- `core.autocrlf = true`. No hay `.gitattributes`.
- `git ls-files --eol`: **todos los archivos versionados tienen LF en el índice**. En la copia de trabajo, 10 tienen CRLF y 24 tienen LF.
- `README.md` y `tests/test_cliente.py` tienen LF en la copia de trabajo. La advertencia *"LF will be replaced by CRLF the next time Git touches it"* solo anuncia la conversión al hacer checkout.
- `src/utils/comparar_modelos_gemini.py` tiene CRLF y se normalizará a LF al agregarlo.
- **Conclusión:** es una **advertencia normal** de `autocrlf` en Windows, **no un problema de consistencia**: el repositorio está normalizado. **No se requiere acción.** Agregar un `.gitattributes` (`* text=auto`) sería una RECOMENDACIÓN TÉCNICA opcional y de baja prioridad.

---

## 13. Arquitectura

**Observaciones** (IMPLEMENTACIÓN VERIFICADA, salvo que se indique otra cosa):

1. **Hay dos clientes HTTP coexistentes.** `src/consumir_gemini.py` responde a todos los errores con `RuntimeError`. `src/cliente.py` reutiliza `armar_peticion` y `extraer_texto`, pero redefine `enviar_peticion` con la clasificación `ValueError`/`TimeoutError`. Es una **evolución intencional y documentada**: `src/cliente.py:4` dice *"Conserva intacto el módulo original del Gate 1"*. `prompts/test_consistencia.py` depende de la versión original. **Recomendación: no unificar.** Unificarlos rompería la trazabilidad del Gate 1 y del banco de prompts.
2. **La separación de responsabilidades es correcta.** `pipeline_texto` y `metricas_texto` son puros y sin red. Los ensayos aíslan las llamadas reales. `construir_cadena` admite la inyección de un modelo falso.
3. **Estado global.** `costo_total_sesion` en `src/cliente.py` es simple y proporcional a un ejercicio didáctico, y las pruebas lo aíslan. Sin acción.
4. **Hay scripts que sobrescriben evidencia** (MEDIO): `ensayo_bloque15.py` (sin protección), `preparar_revision_bloque17.py` (sin protección) y `utils/comparar_modelos_gemini.py` (sin protección). En cambio, `ensayo_bloque16.py` sí es reanudable y no duplica. **RECOMENDACIÓN TÉCNICA:** documentar la advertencia en los README de cada bloque. Cambiar el código es opcional y requiere autorización.
5. **Rutas relativas al directorio de trabajo.** `ensayo_bloque15.py`, `ensayo_bloque16.py` y `preparar_revision_bloque17.py` escriben en `docs/...` de forma relativa. Están documentados con *"ejecutar desde la raíz"*. Es aceptable, pero frágil (BAJO).
6. **`src/cadena_tres_pasos.py:58`.** `except (ValueError, Exception)` es redundante, porque `Exception` ya incluye `ValueError`. Es cosmético (BAJO).
7. **`src/main.py` está vacío.** El README de `HEAD` ya lo advierte. Sin acción, o eliminarlo en el futuro con autorización (BAJO).
8. **Falta de prueba:** `seleccionar_muestra` (Bloque 17) no tiene pruebas unitarias (BAJO, RECOMENDACIÓN TÉCNICA).
9. **Solapamiento de pruebas** entre `test_cliente.py` y `test_cliente_bloque13.py`. Es justificable por la trazabilidad por bloque. Sin acción.

No se recomienda introducir patrones nuevos ni refactorizar: la complejidad actual es proporcional al proyecto.

---

## 14. Plan de corrección

Ningún comando de esta sección se ejecutó. Todos requieren autorización.

| # | Archivo | Hallazgo | Evidencia | Acción propuesta | Prioridad | Riesgo | Autorización |
|---|---|---|---|---|---|---|---|
| A1 | Todo el árbol | Hay cambios sin versionar | `git status` | Crear un respaldo local del estado actual | Alta | Nulo | Requerida |
| A2 | `README.md` | Nota del Bloque 17 sin otra copia | `git diff -- README.md` | Copiar la nota a `docs/entrega-bloque17.md` | Alta | Nulo | Requerida |
| A3 | `README.md` | Documentación general sobrescrita | `git show HEAD:README.md` | Restaurar desde `HEAD` (solo después de A1 y A2) | Alta | Bajo, con respaldo | Requerida |
| A4 | `README-bloque17.md` | Ubicación inconsistente | Los demás están en `docs/` | Mover a `docs/README-bloque17.md` | Media | Bajo | Requerida |
| A5 | `docs/README-bloque15.md`, `docs/README-bloque16.md` | Sin versionar | `git status` | Versionar sin cambios | Media | Nulo | Requerida |
| A6 | `docs/ensayo-bloque18.md` | Plantilla y registro concatenados | Líneas 1–14 | El autor decide si elimina las líneas 1–13 y agrega la fecha y salida reales | Media | Pérdida de la plantilla (recuperable desde Git) | Requerida, decisión del autor |
| A7 | `tests/test_cliente.py` | `HEAD` falla y la versión local corrige | Pytest: 2 fallan en `HEAD`, 18 pasan en local | Conservar la versión local y versionarla | **Alta** | Nulo | Requerida |
| A8 | `requirements.txt` | Falta LangChain | Imports y `pip list` | Agregar `langchain==1.4.8` y `langchain-google-genai==4.4.2` | **Alta** | Bajo | Requerida |
| A9 | `src/utils/comparar_modelos_gemini.py` | Evidencia del ADR sin versionar | `decision-arquitectura.md:31,37` | Versionar sin modificar | Media | Nulo | Requerida |
| A10 | `docs/decision-arquitectura.md` | La ruta citada `utils/…` no coincide con `src/utils/…` | Líneas 31 y 37 | Corregir la ruta en el texto | Baja | Nulo | Requerida |
| A11 | `README.md` (después de A3) | Desactualizado, solo cubre hasta el Gate 1 | Sección 6 | Actualizar en un commit aparte: `.venv`, estructura, pytest, índice de documentos por bloque | Media | Bajo | Requerida |
| A12 | `docs/ensayo-bloque13.md`, `docs/ensayo-bloque14.md` | Evidencia "pendiente" | Contenido | El autor registra ejecuciones reales. **No completar con datos de esta auditoría ni inventados** | Media | — | Decisión del autor |
| A13 | `ia.accenture.ven/` | Entorno virtual sin uso aparente | `pyvenv.cfg` y `.vscode` | Evaluar su eliminación | Baja | Si otro proyecto lo usa (NO VERIFICADO) | Requerida |
| A14 | `src/cadena_tres_pasos.py:58`, `.gitattributes`, prueba de `seleccionar_muestra` | Mejoras menores | Sección 13 | Opcionales, en un commit posterior | Baja | Bajo | Requerida |

### Comandos propuestos, en orden

**1. Preservación del estado actual (A1).** Crea un *stash* de respaldo sin alterar la copia de trabajo:

```powershell
git stash create "respaldo-auditoria-2026-11-02"
# Guardar el hash que devuelve en una referencia nombrada:
git stash store -m "respaldo-auditoria-2026-11-02" <hash_devuelto>
# Respaldo adicional de los archivos no versionados:
New-Item -ItemType Directory -Force ..\respaldo-plantilla-base | Out-Null
Copy-Item README.md, README-bloque17.md ..\respaldo-plantilla-base\
Copy-Item docs\README-bloque15.md, docs\README-bloque16.md ..\respaldo-plantilla-base\
Copy-Item -Recurse src\utils ..\respaldo-plantilla-base\utils
```

**2. Resolución de la sobrescritura del README (A2 y A3):**

```powershell
Copy-Item README.md docs\entrega-bloque17.md
git restore README.md
```

**3. Integración de la documentación pendiente (A4 y A5):**

```powershell
Move-Item README-bloque17.md docs\README-bloque17.md
```

**4. Pruebas (A7).** No requieren cambios. Verificar de nuevo:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

**5. Dependencias (A8).** Edición manual de `requirements.txt` para agregar dos líneas. Después:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --dry-run
```

La validación completa se hace con una instalación limpia en otra carpeta, como en el Gate 1.

**6. Utilidades (A9).** Sin cambios en el código.

**7. Commits controlados** (sección 15), siempre con `git add` explícito por archivo y nunca con `git add .`.

---

## 15. Propuesta de versionamiento

Se proponen **commits separados** para mantener un historial legible:

```powershell
# Commit 1 — corrige la suite publicada
git add tests/test_cliente.py
git commit -m "Actualiza pruebas del cliente al contrato de reintentos del Bloque 13"

# Commit 2 — dependencias del Bloque 18
git add requirements.txt
git commit -m "Declara dependencias de LangChain usadas en el Bloque 18"

# Commit 3 — documentación por bloque
git add docs/README-bloque15.md docs/README-bloque16.md docs/README-bloque17.md docs/entrega-bloque17.md
git commit -m "Versiona instrucciones de los Bloques 15, 16 y 17"

# Commit 4 — evidencia del ADR
git add src/utils/comparar_modelos_gemini.py
git commit -m "Versiona script de benchmark citado en ADR-001"

# Commit 5 — informe de auditoría
git add docs/auditoria-repositorio.md
git commit -m "Agrega informe de auditoria del repositorio"
```

Después, por separado, se pueden hacer las acciones A6, A10 y A11. El `git push origin main` se ejecuta al final, cuando el usuario lo decida.

**No versionar:** `.env`, `.venv/`, `ia.accenture.ven/`, `__pycache__/`, `.pytest_cache/` ni `.vscode/`. Todos están ignorados actualmente.

---

## 16. Conclusión

**Estado verificado:**

- El código de los Bloques 12 a 18 existe, está versionado y su suite local pasa completa: 46 de 46.
- No hay secretos expuestos.
- Los finales de línea están normalizados.

**Pendientes reales:**

1. La sobrescritura de `README.md`, que debe resolverse antes de cualquier commit.
2. La suite publicada en `origin/main` falla en `tests/test_cliente.py`. La copia local la corrige.
3. `requirements.txt` no permite reproducir el Bloque 18.
4. Hay cuatro documentos y un script de evidencia sin versionar.
5. Las evidencias de los Bloques 13 y 14 están en "pendiente", y la del Bloque 18 está duplicada.

**Próximo paso:** autorizar las acciones A1 (respaldo) y luego A2 y A3 (preservar la nota del Bloque 17 y restaurar `README.md`) antes de continuar con el Bloque 19.

### Criterios de finalización

- [x] Se verificó el estado actual de Git.
- [x] Se inspeccionaron los archivos pendientes.
- [x] Se comparó `README.md` con `HEAD`.
- [x] Se revisaron los cambios de `tests/test_cliente.py`, incluida la ejecución de la versión `HEAD`.
- [x] Se inspeccionó `src/utils/`.
- [x] Se revisó la documentación de los bloques. El material oficial del curso **no está disponible** en el repositorio.
- [x] Se analizaron las dependencias existentes. La instalación limpia **no se verificó**.
- [x] Se evaluaron las pruebas automatizadas.
- [x] Se identificaron los riesgos de seguridad.
- [x] Se clasificaron los hallazgos.
- [x] Se preparó un plan de corrección seguro.
- [x] Se generó `docs/auditoria-repositorio.md`.
- [x] No se modificó código ni se ejecutaron commits o pushes.
