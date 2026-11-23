# Gate 2 — Servicio IA modular con RAG

## Objetivo

Demostrar que los componentes de los Bloques 24–32 funcionan como **un único servicio**: índice persistente e incremental, recuperación con citas, defensas contra la inyección de prompt, observabilidad con trazas y consumo, prompt versionado y supervisión humana. La decisión de personalización (Bloques 29–30) se documenta, pero no se implementó con entrenamiento.

## Diagnóstico inicial de compatibilidad

| Componente | Módulo existente | Estado al iniciar el Gate |
|---|---|---|
| Indexación persistente e incremental | `rag.indexador.indexar` / `planificar_indexacion` (Bloques 24–25) | Funcionaba; IDs deterministas, sin duplicados, validación de embeddings |
| Recuperación + small-to-big | `buscar_por_vector_con_score`, `expansion.expandir_hasta_k` (Bloques 26, 28) | Funcionaba; 1 `embed_query` por consulta |
| Filtro, auditoría y consumo | `rag.auditoria.consultar_auditado` (Bloques 31–32) | Funcionaba, pero **solo registraba** las citas inválidas: no rechazaba la respuesta |
| Versionado y LangGraph | `src/gobernanza/` (Bloque 32) | Funcionaba; probado de forma aislada |
| Punto de entrada único y prueba de extremo a extremo con indexación | — | **No existía** |
| Rutas de generación sin defensas | `generador.responder`, `src.recuperar_corpus`, `src.registro_rag`, `src.evaluar_bloque27` | Activas, sin filtro ni auditoría |
| Reproducibilidad | `requirements.txt` | `langgraph` no estaba fijado (llegaba por `langchain`): un entorno limpio instalaba la 1.2.24 en vez de la 1.2.19 probada |

## Qué se agregó

| Archivo | Responsabilidad |
|---|---|
| `src/servicio_rag.py` | `ServicioRAG`, `preparar_indice`, `RespuestaServicio` (contrato), `ModeloSimulado`, modos DEMO y REAL y CLI |
| `src/rag/fundamentacion.py` | Señales heurísticas de relevancia y respaldo de las citas (revisión final) |
| `src/ensayo_gate2.py` | Ensayo funcional de 11 pasos con comprobaciones |
| `src/preflight_gate2.py` | Verificación del entorno para la entrega |
| `src/rubrica_gate2.py` + `data/gate2/autoevaluacion.json` | Rúbrica ponderada con no compensables y autoevaluación con evidencia |
| `tests/test_gate2.py`, `tests/test_fundamentacion_gate2.py`, `tests/test_servicio_gate2.py`, `tests/test_rubrica_gate2.py` | 4 no compensables + integración, fundamentación, contrato y rúbrica |

**Cambios en código existente:**
- `requirements.txt`: se fijaron `langgraph==1.2.19` y `langgraph-checkpoint==4.3.1`.
- Docstrings que marcan como **RUTA HEREDADA** a `rag/generador.responder`, `recuperar_corpus.py`, `registro_rag.py` y `evaluar_bloque27.py`. Su comportamiento no cambió.
- `README.md`: nueva sección del Gate 2, añadida **al final** porque el README es parte del corpus del Bloque 24.
- `src/rag/auditoria.py` (revisión final): campo `RespuestaAuditada.textos_citas`, con el texto de cada unidad `[n]`. Vive solo en memoria y no se escribe en el log; lo usa la validación de respaldo.

## Arquitectura del servicio

```text
ServicioRAG.consultar(pregunta)
└─ rag.auditoria.consultar_auditado            (Bloques 31–32)
   ├─ contexto_traza → trace_id (ContextVar)
   ├─ RecuperadorSmallToBig (BaseRetriever)
   │   ├─ verificar índice no vacío
   │   ├─ embeddings.embed_query  ×1
   │   ├─ buscar_por_vector_con_score (Chroma)
   │   └─ expandir_hasta_k  (unidades finales)
   ├─ filtrar_unidades → cuarentena + evento documento_descartado_por_inyeccion
   ├─ abstención si no queda contexto (sin llamar al modelo)
   ├─ formatear_contexto → citas [1..n] solo con unidades permitidas
   ├─ construir_prompt_seguro (system/human, delimitadores) + identificar_prompt_enviado
   ├─ llamar_con_reintentos(modelo.invoke)  (reintenta solo errores transitorios)
   └─ calcular_metricas → citas_usadas / citas_invalidas ; consumo_llm (extraer_uso, desglose_costo)
└─ validación final del servicio:
   abstención | rechazada_citas_invalidas | rechazada_sin_citas | respondida → evento respuesta_servicio
```

La indexación **no** ocurre al consultar. `preparar_indice` se llama al crear el servicio DEMO:
- crea el índice si la colección no existe;
- lo reutiliza si `planificar_indexacion` no encuentra cambios (no hace ningún `embed_documents`);
- si hay cambios, agrega solo los chunks nuevos.

Los chunks huérfanos de un documento editado se informan, y solo se podan con `podar_huerfanos=True`. La compatibilidad de embeddings se valida antes de escribir.

## Contrato de respuesta

```json
{
  "respuesta": "[SIMULADO] Según la documentación: Los clientes pueden devolver un producto dentro de los 30 días siguientes a la compra, presentando la boleta y el producto sin uso. [1]",
  "fuentes": [{"numero": 1, "documento": "demo/politica_devoluciones.md"}],
  "trace_id": "trace-85557146462c4f308564eae4541ad306",
  "estado": "respondida", "motivo": null, "modo": "simulado",
  "prompt_version": 2, "prompt_huella": "5cbcf92439d0",
  "tokens": {"input_tokens": 506, "output_tokens": 42, "total_tokens": 548},
  "medicion": "simulada", "tiempo_total_ms": 13.314, "costo_estimado_usd": null,
  "fuentes_contexto": [{"numero": 1, "documento": "demo/politica_devoluciones.md"}, {"numero": 2, "documento": "demo/envios.md"}],
  "unidades_descartadas": 1
}
```

(Salida real del ensayo DEMO. Los tokens son una aproximación simulada, caracteres/4, y el costo es `null` porque el modo DEMO no tiene tarifa: no se inventa.)

| `estado` | Cuándo | `fuentes` |
|---|---|---|
| `respondida` | Todas las citas `[n]` existen en el contexto y hay al menos una | Las citadas |
| `abstencion` (`sin_contexto` / `contexto_comprometido`) | No se recuperó nada o todo se descartó por inyección; **no se llama al modelo** | `[]` |
| `abstencion` (`modelo_sin_informacion`) | El modelo declara que la documentación no alcanza | `[]` |
| `rechazada_citas_invalidas` | La respuesta cita un número inexistente; se entrega un texto fijo en vez de la respuesta | `[]` |
| `rechazada_sin_citas` | Respuesta factual sin ninguna cita | `[]` |
| `abstencion` (`fuente_no_pertinente`) | La fuente citada no comparte ninguna raíz con la pregunta (heurística) | `[]` |
| `rechazada_posible_contradiccion` | La oración citada contiene un número o una negación que no está en su fuente (heurística) | `[]` |
| `rechazada_respaldo_insuficiente` | Menos del 50 % de los términos de una oración citada aparecen en su fuente (heurística) | `[]` |

### Tres niveles de validación de citas (revisión final)

| Nivel | Qué comprueba | Cómo | Fiabilidad |
|---|---|---|---|
| 1. Estructural | Que cada `[n]` exista en el contexto entregado | `calcular_metricas` (Bloque 26) | Exacta |
| 2. Relevancia de la fuente | Que la fuente citada trate la pregunta | `rag/fundamentacion.py`: raíces léxicas comunes entre pregunta y fuente | Heurística |
| 3. Respaldo | Que cada oración citada se apoye en su fuente | Cobertura léxica ≥ 0,5, números y negaciones presentes en la fuente | Heurística, **no semántica** |

**Política conservadora:** si una señal heurística falla, el servicio no presenta la respuesta como fundamentada; se abstiene o la rechaza. **No hay verificación semántica** (ni NLI ni juez LLM).

**Falsos negativos fijados como pruebas:** una paráfrasis falsa que usa las mismas palabras y números pasa las heurísticas.

**Falsos positivos fijados como pruebas:** una respuesta correcta con sinónimos («un mes para retornar el artículo») se rechaza.

Las señales (`fundamentacion`) se devuelven en el contrato y se auditan como números, sin texto.

**Caso observado:** con la pregunta «¿Cómo se reembolsa una devolución?», el FAQ pertinente está en cuarentena y el modelo simulado citaba la garantía. La cita era estructuralmente válida pero irrelevante. Ahora termina en `abstencion / fuente_no_pertinente` (0 raíces comunes), y es el paso 12 del ensayo.

## Modos

- **DEMO (predeterminado):**
  - corpus sintético de 4 documentos: una política de devoluciones, envíos, garantía y un FAQ que **solo contiene la inyección en el segundo chunk de su sección**;
  - Chroma en un directorio temporal;
  - `EmbeddingsDemo` (bolsa de palabras) envuelto en `EmbeddingsConReintentos`, que cuenta las llamadas;
  - `ModeloSimulado`, que repite la primera oración del fragmento `[1]`. No evalúa relevancia: es un doble de prueba, no un LLM.
- **REAL (`--real`, optativo):**
  - ejecuta `rag.preflight.ejecutar_preflight` y aborta si hay errores, antes de crear clientes;
  - usa `CONFIG_BLOQUE26_MD` sin indexar, Gemini, tarifas verificadas y `logs/rag_auditoria.jsonl`;
  - **no se ejecutó en el Gate 2**: no hay resultados ni costos del servicio en modo real.

## Estructura relevante

```text
src/servicio_rag.py  ensayo_gate2.py  preflight_gate2.py  rubrica_gate2.py
src/rag/        indexador, recuperador, expansion, auditoria, seguridad_prompt, logging_json, trazabilidad, costos…
src/gobernanza/ registro_prompts, grafo_supervision, matriz_riesgos, almacenamiento_prompts
src/personalizacion/  dataset, validación, decisión (Bloques 29–30)
data/gobernanza/  data/gate2/  data/personalizacion/  data/evaluacion/  data/tarifas_gemini.json
tests/test_gate2.py  test_servicio_gate2.py  test_rubrica_gate2.py  (+ suites de los Bloques 12–32)
docs/README-gate2.md  ensayo-gate2.md  rubrica-gate2.md  entrega-gate2.md
```

## Limitaciones

- La validación de citas es exacta solo en lo estructural. La relevancia y el respaldo se estiman con heurísticas léxicas, **sin verificación semántica**.
- En modo REAL, las paráfrasis de Gemini podrían producir rechazos conservadores de más; no se midió porque no hay respuestas reales guardadas para calibrar (el Bloque 28 registró solo longitudes).
- Los eventos de descarte registran el **encabezado de sección** del documento en cuarentena. Es un metadato, no el contenido, pero en un corpus sensible un encabezado podría revelar información.
- El modo DEMO prueba el flujo, no la calidad de las respuestas; la calidad de recuperación se midió en el Bloque 27 con el índice real.
- Las rutas heredadas siguen disponibles sin defensas.
- La supervisión humana no autentica aprobadores y usa un checkpointer en memoria.
