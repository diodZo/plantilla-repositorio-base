# Matriz de riesgos — Bloque 32

Fuente de datos: `data/gobernanza/matriz_riesgos.json`. Probabilidad (P) e impacto (I) son **estimaciones** del equipo, justificadas con evidencia del repositorio; no son mediciones. El puntaje, la categoría y la sensibilidad los calcula `src/gobernanza/matriz_riesgos.py` con la fórmula y los cortes oficiales del curso:

```python
puntaje = probabilidad * impacto        # P e I: enteros 1–5 (los booleanos se rechazan)
>= 15 CRITICO · >= 9 ALTO · >= 4 MEDIO · resto BAJO
```

Regenerar: `.\.venv\Scripts\python.exe -m src.matriz_riesgos` (la prueba `test_documento_contiene_la_tabla_calculada` comprueba que esta tabla coincide con la calculada).

## Matriz ordenada por puntaje

| ID | Riesgo | P | I | Puntaje | Categoría | Al límite | Supervisión humana | Estado del control |
|---|---|---:|---:|---:|---|---|---|---|
| R06 | Activación de una nueva versión del prompt sin aprobación humana | 3 | 4 | 12 | ALTO | Sí: probabilidad -1 → MEDIO; probabilidad +1 → CRITICO; impacto +1 → CRITICO | Aprobación humana del despliegue de cada versión de prompt (grafo de supervisión) (implementado_probado) | implementado_probado |
| R03 | Rutas antiguas del RAG que envían el prompt del Bloque 26 sin el filtro de inyección | 4 | 3 | 12 | ALTO | Sí: probabilidad +1 → CRITICO; impacto -1 → MEDIO; impacto +1 → CRITICO | Revisión obligatoria de cambios que afecten fuentes, citas o seguridad, y decisión explícita de migrar o retirar las rutas antiguas (propuesto) | documentado_pendiente |
| R02 | Filtración de información sensible desde registros locales que guardan el texto de las consultas | 3 | 3 | 9 | ALTO | Sí: probabilidad -1 → MEDIO; impacto -1 → MEDIO | Autorización explícita antes de acceder, copiar o compartir registros con texto de usuarios (propuesto) | implementado_sin_prueba |
| R04 | Respuestas basadas en un índice Chroma desactualizado respecto de los documentos del corpus | 3 | 3 | 9 | ALTO | Sí: probabilidad -1 → MEDIO; impacto -1 → MEDIO | Revisión humana del resultado de --plan antes de reconstruir o podar un índice (documentado_pendiente) | implementado_probado |
| R01 | Inyección de prompt indirecta en contenido recuperado que supera el detector léxico | 2 | 4 | 8 | MEDIO | Sí: probabilidad +1 → ALTO; impacto +1 → ALTO | Revisión humana de las unidades en cuarentena (evento documento_descartado_por_inyeccion) y detención con derivación a revisión ante contenido sospechoso (propuesto) | implementado_probado |
| R07 | Pérdida de las solicitudes de aprobación pendientes al reiniciar el proceso | 4 | 2 | 8 | MEDIO | Sí: probabilidad +1 → ALTO; impacto +1 → ALTO | Checkpointer durable (SQLite) para retomar la misma solicitud con el mismo thread_id (propuesto) | implementado_probado |
| R05 | Consulta con un modelo o dimensión de embeddings distinto del usado al indexar | 2 | 2 | 4 | MEDIO | Sí: probabilidad -1 → BAJO; impacto -1 → BAJO | Revisión antes de reconstruir un índice con otro modelo de embeddings (documentado_pendiente) | implementado_probado |
| R08 | Falsos positivos del detector que descartan contenido legítimo | 2 | 2 | 4 | MEDIO | Sí: probabilidad -1 → BAJO; impacto -1 → BAJO | Revisión humana periódica de la cuarentena para ajustar patrones (propuesto) | implementado_probado |

**Al límite** significa que cambiar en ±1 una sola variable, sin salir de 1–5, cambia la categoría.

## Lectura

- **4 riesgos ALTO** (R06, R03, R02, R04), ninguno CRITICO. Todos tienen un control humano identificado, pero solo el de **R06** está implementado y probado. Los de R02 y R03 son **propuestos** y el de R04 está **documentado pero pendiente**.
- **Los 8 riesgos están al límite.** Con puntajes entre 4 y 12, cualquier ajuste de un punto cruza un corte (4, 9 o 15). La clasificación es frágil y debe revisarse cuando cambie la evidencia: por ejemplo, R03 pasaría a CRITICO con P = 5 si las rutas antiguas se usaran con un corpus externo.
- **Brecha de R01 (inyección):** el criterio del curso pide detener el procesamiento automático y derivar a revisión ante contenido sospechoso. El comportamiento actual (Bloque 31) descarta la unidad y **continúa**. Por eso la mitigación técnica figura como implementada y probada, pero el control humano asociado figura como **propuesto**.

## Detalle por riesgo

### R06 — Activación de una nueva versión del prompt sin aprobación (P3 × I4 = 12, ALTO)
- **Evidencia:** `src/gobernanza/grafo_supervision.py` y `src/gobernanza/registro_prompts.py`. El texto enviado vive en `src/rag/seguridad_prompt.py`.
- **Probabilidad 3:** el registro y el grafo impiden activar sin aprobación, pero un commit que edite el código cambia el prompt efectivo sin pasar por el registro. Así llegó v2, sin aprobación formal registrada.
- **Impacto 4:** el prompt de sistema define las reglas de seguridad y de citación de todas las consultas auditadas.
- **Mitigación:** huellas SHA-256, grafo con `interrupt`, validaciones estrictas y la identificación en cada consulta auditada del prompt realmente enviado (`prompt_registrado`, `prompt_es_activa`).
- **Limitaciones:** no hay autenticación de aprobadores; un cambio no aprobado por commit se **detecta** después de ocurrir, no se impide.
- **Supervisión:** aprobación humana del despliegue. **Implementada y probada** (`tests/test_grafo_supervision.py`, `tests/test_integracion_gobernanza.py`).

### R03 — Rutas antiguas sin filtro de inyección (P4 × I3 = 12, ALTO)
- **Evidencia:** `generador.responder`, `src/recuperar_corpus.py`, `observabilidad.consultar_instrumentado` (`src.registro_rag`) y `src/evaluar_bloque27.py` usan `construir_prompt` (v1).
- **Probabilidad 4:** son los CLI documentados en los README 26–28.
- **Impacto 3:** conservan roles y delimitadores; el daño depende de que haya contenido malicioso en el corpus interno.
- **Supervisión:** revisión obligatoria de cambios de seguridad y decisión explícita de migrar o retirar esas rutas. **Propuesta.**

### R02 — Registros locales con texto de consultas (P3 × I3 = 9, ALTO)
- **Evidencia:** `observabilidad.py` guarda `pregunta`; `agente_bloque23.registrar_traza` guarda `entrada`, argumentos y observaciones. `.gitignore` los excluye.
- **Mitigación:** `.gitignore`, `preflight.comprobar_staging` (sin prueba específica) y log del Bloque 31 sin contenido.
- **Supervisión:** autorización explícita antes de acceder, copiar o compartir registros. **Propuesta.**

### R04 — Índice desactualizado frente al corpus (P3 × I3 = 9, ALTO)
- **Evidencia:** `planificar_indexacion`, `--plan` y `--podar-huerfanos` son manuales; `preflight.comprobar_indice` no mide la frescura del índice.
- **Mitigación:** reindexación incremental probada (`test_rag_indexacion`, `test_rag_consolidacion`).
- **Supervisión:** revisar el resultado de `--plan` antes de reconstruir o podar. **Documentada (README 26, plan RAG) pero pendiente:** no hay aprobación registrada.

### R01 — Inyección indirecta que supera el detector (P2 × I4 = 8, MEDIO)
- **Probabilidad 2:** el corpus es interno, pero hay 5 falsos negativos documentados.
- **Impacto 4:** el modelo podría ignorar reglas, inventar citas o revelar instrucciones.
- **Supervisión:** revisión de la cuarentena y detención con derivación a revisión. **Propuesta** (brecha frente al criterio del curso).

### R07 — Pérdida de solicitudes pendientes al reiniciar (P4 × I2 = 8, MEDIO)
- **Evidencia:** `InMemorySaver` no es durable. `langgraph-checkpoint-sqlite` no está instalado; `pip install --dry-run` indica que la versión 3.1.3 se instalaría sin conflictos.
- **Impacto 2:** falla de forma segura. La propuesta queda en `propuesta` y `GestorSupervision.huerfanas()` la detecta (probado).
- **Supervisión:** checkpointer durable. **Propuesto.**

### R05 — Embeddings incompatibles con el índice (P2 × I2 = 4, MEDIO)
- **Mitigación:** `EmbeddingsIncompatiblesError` al cargar o consultar (probado en `test_rag_indexacion`). Falla de forma cerrada.
- **Supervisión:** revisión antes de reconstruir con otro modelo. **Documentada, pendiente.**

### R08 — Falsos positivos del detector (P2 × I2 = 4, MEDIO)
- **Evidencia:** 0 de 83 chunks y 1 de 1186 párrafos marcados (informe del Bloque 31).
- **Mitigación:** evento de descarte con fuente, patrón y huella; abstención.
- **Supervisión:** revisión periódica de la cuarentena. **Propuesta.**

## Controles humanos por estado

| Estado | Controles |
|---|---|
| Implementado y probado | Aprobación del despliegue de versiones de prompt (R06) |
| Documentado, pendiente | Revisión de `--plan` antes de reconstruir o podar (R04); revisión antes de cambiar el modelo de embeddings (R05) |
| Propuesto | Migración o retiro de rutas antiguas (R03); autorización de acceso a registros (R02); revisión de cuarentena y detención ante contenido sospechoso (R01, R08); checkpointer durable (R07) |
