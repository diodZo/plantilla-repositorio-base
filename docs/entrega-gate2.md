# Entrega Gate 2 — Evidencias consolidadas

Fecha: 23 de noviembre de 2026 · Python 3.13.5 · Windows 11. No se llamó a Gemini, no se entrenó ningún modelo y no se reindexó el corpus real. El estado de la entrega es una **autoevaluación** (`LISTO_PARA_REVISION`), no una aprobación oficial.

## 1. Pipeline funcional (Unidad 2.5)

Servicio único `src/servicio_rag.py` sobre los módulos existentes (ver `docs/README-gate2.md`). El ensayo DEMO (`python -m src.ensayo_gate2`) superó **12/12** comprobaciones (revisión final):
- indexación;
- recuperación con un embedding;
- filtrado tras la expansión;
- generación simulada;
- citas válidas;
- auditoría con un único trace_id;
- consumo simulado;
- abstención por contexto comprometido;
- reutilización del índice e indexación incremental;
- supervisión;
- abstención por fuente no pertinente.

Detalle en `docs/ensayo-gate2.md`.

**Modo REAL:** implementado (`--real`, con preflight previo), pero **no ejecutado** en el Gate 2.

## 2. Recuperación y citación (Bloque 27, resultados históricos reales)

Fuente: `docs/resultados_evaluacion_bloque27.md`.
- **Dataset:** `data/evaluacion/bloque27_casos.json`, huella `9e7782ea8474`; 12 casos (10 con respuesta y 2 sin respuesta).
- **Índice real:** `corpus_proyecto_bloque24_md`, 261 chunks, 8 documentos y 57 secciones.

| Configuración | k | Precision | Recall | F1 | Hit |
|---|---|---|---|---|---|
| índice original (chunk) | 3 | 0,367 | 0,800 | 0,490 | 0,800 |
| markdown (chunk) | 3 | 0,333 | 0,750 | 0,450 | 0,800 |
| **markdown expandido (sección)** — elegida | **3** | **0,417** | **0,950** | **0,560** | **1,000** |
| markdown expandido (sección) | 5 | 0,300 | 1,000 | 0,444 | 1,000 |
| markdown híbrido expandido | 3 | 0,350 | 0,800 | 0,470 | 0,900 |

**Configuración elegida:** markdown + expansión por sección con k=3. Tiene el mejor F1 y recall a k=3 con menos contexto que k=5. Es la que usa el servicio.

**Limitaciones:**
- Con 10 casos con respuesta, un caso pesa 0,1.
- El etiquetado lo hizo el desarrollador del sistema.
- La métrica mide la recuperación, no la calidad de la respuesta.
- Las métricas de sección no son comparables uno a uno con las de chunk.

No se hicieron mediciones nuevas en el Gate 2.

**Citación en el servicio:**
- Las citas `[1..n]` se reconstruyen solo con las unidades permitidas.
- La respuesta se rechaza si cita un número inexistente o no cita nada.
- Las pruebas verifican que no se cita la fuente descartada.

**Revisión final — tres niveles de validación, distintos entre sí:**

1. **Estructural (exacto):** la cita existe en el contexto entregado.
2. **Relevancia de la fuente (heurística léxica):** al menos una raíz común entre la pregunta y la fuente citada.
3. **Respaldo (heurística léxica, no semántica):** en cada oración citada, cobertura de términos ≥ 0,5, y sus números y negaciones presentes en la fuente.

No hay verificación semántica. La política es conservadora: abstención o rechazo ante cualquier señal negativa.

El caso observado (pregunta sobre reembolsos con una cita válida a la garantía) ahora termina en `abstencion / fuente_no_pertinente`.

Límites fijados como pruebas en `tests/test_fundamentacion_gate2.py`:
- **Pasa (falso negativo):** una paráfrasis falsa con las mismas palabras.
- **Se rechaza (falso positivo):** una respuesta correcta con sinónimos.

## 3. Costo y latencia (Bloque 28, 5 consultas reales)

Fuente: `docs/resultados_bloque28.md` (versionado). El JSONL original `registros_latencia_costo.jsonl` está ignorado por Git porque contiene las preguntas. No se gastaron llamadas nuevas.

| Medida (n = 5) | Media | Mediana | Mín. | Máx. |
|---|---|---|---|---|
| Total (ms) | 2747,66 | 2314,32 | 1136,20 | 5813,73 |
| embed_query (ms) | 737,69 | 427,04 | 364,94 | 1250,82 |
| Búsqueda vectorial (ms) | 6,80 | 5,74 | 3,48 | 11,12 |
| Generación (ms) | 1965,92 | 1056,51 | 761,36 | 5317,53 |
| Tokens de entrada | 970,00 | 929 | 735 | 1299 |
| Tokens de salida | 83,20 | 92 | 26 | 123 |
| Costo de generación estimado (USD) | 0,00049900 | 0,00050870 | 0,00028550 | 0,00061970 |

**k=3 frente a k=6** (caso `c07-aprobacion`):

| k | Tokens de entrada | Total (ms) | Costo (USD) | Secciones | Fuentes |
|---|---|---|---|---|---|
| 3 | 929 | 1136,2 | 0,00050870 | 3 | iguales |
| 6 | 1299 | 1415,8 | 0,00061970 | 6 | iguales |

Con k=6 entran 370 tokens más (+40 %) y el costo sube un 22 %, con las mismas fuentes.

**Notas sobre las cifras:**
- Tarifas verificadas el 16/11/2026 (USD 0,30 / 2,50 por millón de tokens).
- **Costo estimado ≠ facturación:** depende del nivel gratuito o de pago, la caché y los descuentos.
- La API no reporta tokens para el embedding de consulta.
- Con n = 5, las cifras describen esas ejecuciones, no el rendimiento habitual.

## 4. Personalización (Unidad 2.6, Bloques 29–30)

Fuentes: `docs/decision_personalizacion.md`, `docs/README-bloque29.md` y `docs/README-bloque30.md`.

**Tarea:** clasificar mensajes de error del proyecto en un JSON `{categoria, accion_sugerida}`. Dataset propio validado: 25 ejemplos de entrenamiento + 10 de validación, 5 categorías balanceadas.

**Método de decisión con los pesos oficiales del curso:**

| Criterio | RAG | FT completo | PEFT | Valor comprobado |
|---|---:|---:|---:|---|
| Información cambia seguido | 3 | 0 | 0 | Sí (parcial: 4 commits del catálogo de errores en 30 días) |
| Problema de formato o tono | 0 | 1 | 2 | **No verificado** (no hay muestra de 20 respuestas) |
| Dataset grande y de calidad | 0 | 2 | 1 | No (35 < 200) |
| Presupuesto limitado / iterar rápido | 2 | 0 | 1 | Sí (parcial: cuota gratuita y errores 429) |
| Múltiples variantes | 0 | 0 | 2 | No (parcial) |

**Resultados:**

| Escenario | RAG | FT completo | PEFT | Primer lugar |
|---|---:|---:|---:|---|
| Criterios comprobados (**provisional**) | 5 | 0 | 1 | RAG |
| Hipótesis inicial | 2 | 1 | 3 | PEFT |
| Ejemplo oficial del curso | 0 | 3 | 3 | Empate FT/PEFT |

**Decisión:** **Prompt + Pydantic** como primera solución, con el catálogo de errores como contexto actualizable y un esquema `SalidaClasificacion` estricto. **PEFT** queda como evolución futura si la línea base incumple el formato en al menos 15 % de 20 respuestas reales.

**Restricciones del SDK:** con google-genai 2.34.0, PEFT solo es enviable en modo Vertex con dataset en Cloud Storage.

**No se entrenó ningún modelo:** solo se preparó y validó el dataset.

## 5. Observabilidad

- `logs/rag_auditoria.jsonl`, ignorado por Git.
- Por consulta: `consulta_recibida → recuperacion_iniciada → recuperacion_finalizada → documento_descartado_por_inyeccion → contexto_filtrado → generacion_iniciada (con versión y huella del prompt) → generacion_finalizada → consumo_llm → consulta_finalizada → respuesta_servicio`, todos con el mismo `trace_id`.
- **Privacidad:** la prueba `test_logs_sin_contenido_crudo` lee el archivo JSONL real y verifica que no contiene el correo sintético, la pregunta, el contenido de los documentos, el texto del prompt ni una clave `AIza…` presente en el entorno.

## 6. Seguridad y gobernanza (Unidad 2.7)

- **Inyección:**
  - filtro sobre las unidades finales tras la expansión;
  - casos probados: documento limpio, inyección directa, inyección que solo aparece al expandir, documentos mezclados, todo descartado (abstención sin llamar al modelo) y falso positivo conocido (documentación que describe `<contexto>`);
  - riesgos residuales en `docs/informe_seguridad_bloque31.md`.
- **Versionado:** v1 `10915cb400b1` (Bloque 26) y v2 `5cbcf92439d0` (Bloque 31, activa). Cada respuesta informa `prompt_version` y `prompt_huella` del texto realmente enviado.
- **Supervisión humana:**
  - grafo LangGraph real del Bloque 32 sobre una copia del registro;
  - el grafo pausa en `solicitar_supervision` y nada se activa antes de aprobar;
  - un `Command(resume=True)` de un agente no autoriza;
  - la aprobación activa la propuesta y el rechazo conserva la versión anterior;
  - las decisiones son **simuladas**; **no hay autenticación de aprobadores** y el checkpointer está en memoria (no durable).
- **Matriz de riesgos** (umbrales oficiales sin cambios, ver `docs/matriz_riesgos_bloque32.md`):

| ID | Riesgo | P×I | Categoría | Control humano | Estado del control |
|---|---|---|---|---|---|
| R06 | Activar un prompt sin aprobación | 3×4 = 12 | ALTO | Aprobación de despliegue | implementado y probado |
| R03 | Rutas heredadas sin filtro | 4×3 = 12 | ALTO | Revisión y retiro de rutas | propuesto |
| R02 | Registros con texto de consultas | 3×3 = 9 | ALTO | Autorización de acceso | propuesto |
| R04 | Índice desactualizado | 3×3 = 9 | ALTO | Revisión de `--plan` | documentado, pendiente |
| R01 | Inyección que supera el detector | 2×4 = 8 | MEDIO | Revisión de cuarentena | propuesto |
| R07 | Pérdida de solicitudes al reiniciar | 4×2 = 8 | MEDIO | Checkpointer durable | propuesto |
| R05 | Embeddings incompatibles | 2×2 = 4 | MEDIO | Revisión antes de reconstruir | documentado, pendiente |
| R08 | Falsos positivos del detector | 2×2 = 4 | MEDIO | Revisión de cuarentena | propuesto |

  Los 8 riesgos están al límite de su categoría. Solo el control de R06 está implementado y probado.

## 7. Pruebas

| Suite | Resultado |
|---|---|
| `tests/test_gate2.py` | 23 passed (incluye los 4 no compensables) |
| `tests/test_fundamentacion_gate2.py` | 16 passed (revisión final) |
| `tests/test_servicio_gate2.py` | 8 passed |
| `tests/test_rubrica_gate2.py` | 22 passed |
| Suite completa (`.venv`, revisión final) | **647 passed**, 10 warnings (las mismas advertencias de deprecación preexistentes de `RunnableWithMessageHistory`). Antes del Gate: 578; primera entrega: 631 |
| `python -m src.rubrica_gate2` | Los 4 no compensables CUMPLEN, ejecutados contra el servicio integrado |

## 8. Reproducibilidad

Se verificó sin tocar `.venv`, en un entorno alternativo temporal creado con el Python base 3.13.5:

1. **Instalación limpia:** `python -m venv` + `pip install -r requirements.txt` terminó correctamente.
   - **Hallazgo:** `langgraph` no estaba fijado. El entorno limpio instaló **1.2.24**, mientras que todo se había probado con **1.2.19**.
   - **Corrección controlada** (sin `pip freeze`): se fijaron `langgraph==1.2.19` y `langgraph-checkpoint==4.3.1`, porque el Bloque 32 los importa directamente.
   - Tras reinstalar: `pip check` → «No broken requirements found»; langgraph 1.2.19 y langgraph-checkpoint 4.3.1.
2. **Suite en el entorno limpio** (árbol de trabajo actual): **631 passed**, 10 warnings.
3. **Clon simulado:** se copió solo lo que incluiría un commit (`git ls-files --cached --others --exclude-standard`): sin `.git`, `.env`, `vectorstore/`, `logs/` ni registros. Con el entorno limpio:
   - **630 passed, 1 skipped.** La omitida es `test_versiones_comprobadas_contra_el_historial_git`, que necesita el historial de git y lo indica explícitamente.
   - `python -m src.ensayo_gate2` → 11/11.
   - `python -m src.servicio_rag` → código 0. El modo DEMO funciona **sin `.env`**.

**Reverificación tras el cambio del README y la validación de fundamentación (revisión final):**
- **Entorno limpio:** `pip install -r requirements.txt` OK, `pip check` sin conflictos, suite **647 passed**.
- **Clon simulado nuevo:** **646 passed, 1 skipped** (la misma omisión de git), ensayo **12/12** y servicio con código 0.
- **Preflight en el clon:** 0 errores y 2 advertencias esperadas: no hay índice real (el modo DEMO no lo necesita) y no hay `.git` para listar archivos.
- **Dataset congelado del Bloque 27:**
  - sin cambios (`git diff` vacío en `data/evaluacion/`);
  - carga congelado (2026-11-16T22:51:22+00:00, huella `9e7782ea8474`);
  - `test_etiquetas_reales_coinciden_con_el_chunking_determinista` pasa;
  - no se modificó ninguna etiqueta.

**Pendiente:**
- Un `git clone` real tras el commit, que solo es posible después de que el usuario confirme.
- La instalación en otro sistema operativo; solo se verificó en Windows 11.

## 9. Autoevaluación

Promedio ponderado **81,75** (umbral 80), con los 4 no compensables verificados → `LISTO_PARA_REVISION`. Detalle en `docs/rubrica-gate2.md`. **No es la aprobación oficial.**

## 10. Pendientes y riesgos

- **Índice real desactualizado (R04, evidencia concreta):**
  - `README.md` forma parte del corpus del Bloque 24 y se le agregó la sección del Gate 2.
  - `planificar_indexacion` (solo lectura, sin embeddings) informa **23 chunks nuevos** de `README.md`, 261 ya existentes y 0 huérfanos.
  - No se reindexó (restricción del Gate). Hasta ejecutar `python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md --plan` y luego la indexación incremental, el modo REAL no verá esa sección.
  - La sección se agregó **al final** del README: insertarla al principio desplazaba los chunks y rompía las etiquetas congeladas del Bloque 27 (`test_etiquetas_reales_coinciden_con_el_chunking_determinista`).
- Ejecutar el modo REAL del servicio (con autorización y costo) y registrar el resultado aparte del DEMO. El preflight real (`python -m src.rag.preflight`) dio 0 errores. Los comandos exactos, identificados y **no ejecutados**, están en `docs/ensayo-gate2.md` §4.3.
- Calibrar las heurísticas de fundamentación con respuestas reales de Gemini: podrían rechazar paráfrasis correctas.
- Migrar o retirar las rutas heredadas (R03).
- Hacer que la cuarentena derive a revisión humana en lugar de descartar y continuar (brecha de R01).
- Autenticación de aprobadores y checkpointer durable (R06, R07).
- Medir la línea base Prompt + Pydantic con respuestas reales antes de considerar PEFT.
- Validación semántica de citas (NLI, juez LLM o revisión humana). Hoy es exacta en lo estructural y heurística en relevancia y respaldo.
