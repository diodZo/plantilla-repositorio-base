# Bloque 32 — Versionado de prompts, supervisión humana y matriz de riesgos

## Objetivos (cierre de la Unidad 2.7)

1. **Registro de versiones** del prompt real del RAG, con huellas SHA-256, diff y estados de aprobación.
2. **Supervisión humana** con LangGraph (`StateGraph`, `START`, `END`, `interrupt`, `Command`, `InMemorySaver`): ninguna versión se activa sin una decisión humana explícita.
3. **Matriz de riesgos** del proyecto con la fórmula y las categorías oficiales, análisis de sensibilidad y control humano para todo riesgo ALTO o CRITICO.

No se llamó a Gemini, no se entrenó ni se reindexó nada, y ninguna demostración modifica el registro versionado ni el prompt que usan las rutas del RAG.

## Arquitectura

| Archivo | Responsabilidad |
|---|---|
| `src/gobernanza/almacenamiento_prompts.py` | JSON con escritura atómica (temporal + `fsync` + `os.replace`), validación de esquema, rechazo de secretos y persistencia separada de solicitudes |
| `src/gobernanza/registro_prompts.py` | `RegistroDePrompts`, `diff_prompts`, huellas, las dos versiones reales y `identificar_prompt_enviado` (integración con el Bloque 31) |
| `src/gobernanza/grafo_supervision.py` | Grafo LangGraph y `GestorSupervision` (iniciar, pendiente, resolver, huérfanas) |
| `src/gobernanza/matriz_riesgos.py` | `categoria_riesgo`, `esta_en_el_limite`, carga y validación de la matriz y tabla Markdown |
| `src/registro_prompts.py`, `src/grafo_supervision.py`, `src/matriz_riesgos.py` | Los tres CLI de entrega |
| `data/gobernanza/registro_prompts.json` | Registro versionado: v1 y v2 reales |
| `data/gobernanza/matriz_riesgos.json` | 8 riesgos con P, I, justificaciones, evidencia y controles |

**Cambio en código anterior:** `src/rag/auditoria.py` añade la identificación del prompt al evento `generacion_iniciada` y el campo `RespuestaAuditada.prompt`. No cambia el texto enviado ni la recuperación, los filtros o las métricas. Ningún otro módulo de los Bloques 12–31 se modificó.

**Dependencias:** ninguna nueva. Se usa langgraph 1.2.19 / langgraph-checkpoint 4.3.1, que ya estaban instalados.

## Qué se versiona y cómo se calcula la huella

El prompt RAG tiene dos mensajes (sistema y humano). Se versiona su **material estático**: la plantilla del sistema y la plantilla humana con los marcadores `{contexto}` y `{pregunta}`, unidas en un texto canónico:

```text
### system
<plantilla system>
### human
<plantilla human>
```

`huella` = `sha256(texto).hexdigest()[:12]` (huella corta del curso) y `huella_completa` = digest de 64 caracteres. El contexto y la pregunta son datos de cada consulta y no forman parte de la versión. El registro guarda el texto completo, así que cualquier versión se reconstruye y su huella se vuelve a verificar al cargar el archivo.

## Versiones reales

El historial de git contiene **dos versiones comprobables** del prompt RAG, así que no hizo falta inventar una segunda:

| Versión | Huella | Origen | Autor y fecha (git) | Estado |
|---|---|---|---|---|
| v1 | `10915cb400b1` | `08565c9` `src/rag/prompts.py` (Bloque 26) | dortiz, 2026-11-12T21:53:09-03:00 | `reemplazada` en la ruta auditada; las rutas antiguas aún la envían |
| v2 | `5cbcf92439d0` | `f5421dc` `src/rag/seguridad_prompt.py` (Bloque 31) | dortiz, 2026-11-19T22:18:42-03:00 | `activa` (la envía `consultar_auditado`) |

- La prueba `test_versiones_comprobadas_contra_el_historial_git` verifica con `git show` y `git log` que los textos y metadatos existen tal cual en esos commits.
- `modelo_validado` y `parametros_validados` quedan en `null`: no hay registro de una validación.
- v2 llegó por commit **sin aprobación formal registrada**, y así lo dice su nota.
- Las propuestas de las demostraciones (v3 con «regla 9», y otra que debilita la regla 3) son **propuestas académicas**: solo existen en copias temporales.

Diff real v1 → v2: se añaden exactamente la regla 8 y la línea de aviso del mensaje humano (ver `docs/evidencia_bloque32.md`).

## Estados y almacenamiento

- **Estados:** `propuesta` → `activa` (solo con `aprobar` y una decisión humana válida) o `rechazada`; la activa anterior pasa a `reemplazada`.
- **Altas:** `registrar` solo admite `propuesta`, salvo la evidencia histórica de git. La última versión registrada no se confunde con la activa (métodos `ultima()` y `activa()`).
- **Integridad:** se rechazan los duplicados de texto (`VersionDuplicadaError`) y los textos con apariencia de credencial (`SecretoEnPromptError`). Al cargar se verifican la huella contra el texto, la unicidad de `nombre`+`version` y que haya como máximo una versión activa.
- **Archivo corrupto:** se lanza `AlmacenCorruptoError` y **no se sobrescribe ni se repara**. El registro está versionado en git y puede restaurarse.
- **Solicitudes de aprobación:** van en un archivo aparte (`solicitudes.json` en las demostraciones), distinto del registro.

## Supervisión humana con LangGraph

```text
START → proponer → solicitar_supervision ─interrupt()─▶ (decisión humana)
                       ▲         │
                       └─ inválida (≤3) ─┤
                                 ├─ aprobada  → aplicar   → END  (activa la nueva huella)
                                 ├─ rechazada → conservar → END  (mantiene la anterior)
                                 └─ 3 inválidas → sin_decision → END (nada se activa)
```

- `proponer` registra la propuesta y el diff. `solicitar_supervision` no tiene efectos antes de `interrupt()`, porque LangGraph vuelve a ejecutar el nodo al reanudar.
- **Validaciones de `GestorSupervision.resolver`:**
  - el hilo existe (`get_state` con valores);
  - hay una interrupción pendiente y el hilo no está resuelto;
  - `aprobado` es un `bool` estricto;
  - la huella revisada existe en el registro y coincide con la pendiente.
- **Validaciones del grafo:**
  - el valor de reanudación es un dict con las claves exactas;
  - el origen está declarado;
  - el **código de confirmación** se generó al iniciar y solo se guarda su SHA-256 en el estado.
- `aplicar` rechaza una aprobación obsoleta (si la versión activa cambió desde la propuesta) y `aprobar` impide la doble aplicación.
- **Hallazgos de LangGraph 1.2.19, verificados en pruebas:**
  1. Un `Command(resume=...)` sobre un hilo ya resuelto **no falla**: devuelve el estado final. Por eso el gestor lo bloquea antes de reanudar.
  2. Si un nodo lanza una excepción tras reanudar, LangGraph **conserva el valor recibido** y lo reutiliza en el siguiente intento. Por eso el grafo no lanza ante una decisión inválida: la registra y vuelve a interrumpir.
- **Autorización:** un `Command(resume=True)` generado por un agente no es un dict válido ni conoce el código, así que no aprueba. **No hay autenticación de aprobadores**: el código es una confirmación de intención, no una identidad verificada. Las decisiones de la demostración están marcadas como `simulada_demo`; `--interactivo` usa `humano_cli`.

### Persistencia del estado

- `InMemorySaver` **no es durable**: si el proceso termina, la solicitud pendiente se pierde. Falla de forma segura: la propuesta queda en `propuesta` y `huerfanas()` detecta la solicitud.
- Con el **mismo** checkpointer, un gestor nuevo retoma el mismo `thread_id` (probado).
- `langgraph-checkpoint-sqlite` **no está instalado**; `pip install --dry-run` indica que la versión 3.1.3 se instalaría sin conflictos (añade `aiosqlite` y `sqlite-vec`). Como la misión condiciona esa demostración a que esté instalado, no se añadió la dependencia; queda como control propuesto para R07.

## Integración con el Bloque 31

En cada consulta auditada, el evento `generacion_iniciada` (con el `trace_id` de la consulta) incluye:

`prompt_nombre`, `prompt_registrado`, `prompt_version`, `prompt_huella`, `prompt_estado`, `prompt_es_activa`, `prompt_version_activa`, `prompt_huella_activa`, `prompt_huella_sistema_enviado` y, si corresponde, `prompt_motivo`.

- **La versión se identifica comparando los mensajes realmente enviados con cada versión registrada.** El mensaje de sistema debe ser idéntico; en el mensaje humano, todo el texto estático debe coincidir y solo los marcadores pueden contener datos. Si nada coincide, `prompt_version` queda en `null`: nunca se atribuye una versión que no se usó.
- `prompt_huella_sistema_enviado` es el SHA-256 (12 caracteres) del mensaje de sistema exacto que se envió.
- **No hay sustitución automática.** Activar otra versión en el registro **no** cambia el texto enviado: la consulta lo informa con `prompt_es_activa=false` (probado).
- Si el registro está corrupto o no existe, la consulta continúa con `prompt_registrado=false` y `prompt_motivo="registro_no_disponible: ..."`.
- Solo se identifica la ruta auditada. Las rutas antiguas no registran versión (riesgo R03).

## Matriz de riesgos

Ver `docs/matriz_riesgos_bloque32.md`. Son 8 riesgos: 4 ALTO (R06, R03 = 12; R02, R04 = 9) y 4 MEDIO (R01, R07 = 8; R05, R08 = 4). **Los 8 están al límite.** Todos los ALTO tienen control humano identificado; solo el de R06 está implementado y probado.

## Comandos

```powershell
.\.venv\Scripts\python.exe -m src.registro_prompts                    # solo lectura + diff v1→v2
.\.venv\Scripts\python.exe -m src.registro_prompts --demo-propuesta   # propuesta en copia temporal
.\.venv\Scripts\python.exe -m src.grafo_supervision                   # aprobación, rechazo y reinicio (simulados)
.\.venv\Scripts\python.exe -m src.grafo_supervision --interactivo     # decisión escrita por una persona
.\.venv\Scripts\python.exe -m src.matriz_riesgos                      # matriz, supervisión y límites
.\.venv\Scripts\python.exe -m src.matriz_riesgos --json
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

## Pruebas

| Archivo | Pruebas |
|---|---:|
| `tests/test_registro_prompts.py` | 27 |
| `tests/test_grafo_supervision.py` | 24 |
| `tests/test_matriz_riesgos.py` | 67 |
| `tests/test_integracion_gobernanza.py` | 9 |
| **Suite completa** | **578 passed** (451 del Bloque 31 + 127 nuevas) |

## Limitaciones y riesgos residuales

- No hay autenticación de aprobadores ni separación de roles entre quien propone y quien aprueba.
- El prompt efectivo está en el código: un commit puede cambiarlo sin pasar por el registro. Se detecta después en la auditoría (`prompt_registrado` / `prompt_es_activa`), pero no se impide.
- `InMemorySaver` no es durable; el checkpointer SQLite está pendiente.
- Las rutas antiguas del RAG siguen sin filtro ni identificación de prompt (R03).
- La cuarentena del Bloque 31 descarta y continúa; no deriva a revisión humana (brecha de R01).
- Probabilidad e impacto son estimaciones; los 8 riesgos están al límite de su categoría.
