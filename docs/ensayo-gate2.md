# Ensayo Gate 2 — Registro de la ejecución

Fecha: 23 de noviembre de 2026 · Python 3.13.5 · Windows 11 · modo DEMO (simulado). No se probó el modo REAL.

## 1. Preflight — `python -m src.preflight_gate2`

Primera ejecución: 1 error real, la falta de los documentos del Gate (`README-gate2`, `ensayo-gate2`, `rubrica-gate2` y `entrega-gate2`), que se crearon después. El resto quedó en OK:
- Python 3.13.5 y los 14 requisitos con la versión fijada.
- `.env`, `.venv/` y `vectorstore/` ignorados.
- Modelos: `gemini-3.5-flash-lite` / `models/gemini-embedding-001`, con tarifas verificadas.
- Índice real `corpus_proyecto_bloque24_md`, leído sin modificarlo: 261 chunks, 8 documentos, todos con `fuente` y modelo de embeddings coherente.
- Registro de prompts: el código envía v2, que es la activa.
- Matriz: 8 riesgos y ningún ALTO/CRITICO sin control humano.
- Secretos: 193 archivos destinados al commit, sin credenciales.

## 2. Ensayo funcional — `python -m src.ensayo_gate2`

```text
  [OK] 01_corpus_sintetico
  [OK] 02_indice_creado
  [OK] 03_recuperacion_un_embedding
  [OK] 04_filtrado_tras_expansion
  [OK] 05_generacion_simulada
  [OK] 06_citas_validas
  [OK] 07_auditoria_trace_unico
  [OK] 08_consumo_simulado
  [OK] 09_abstencion_sin_contexto_confiable
  [OK] 10_segunda_corrida_reutiliza_indice
  [OK] 11_supervision_humana

Indexación: inicial={'accion': 'creado', 'chunks_corpus': 5, 'agregados': 5, 'huerfanos': 0, 'podados': 0, 'conteo': 5}
            reutilizada={'accion': 'reutilizado', 'chunks_corpus': 5, 'agregados': 0, 'huerfanos': 0, 'podados': 0, 'conteo': 5}
            incremental={'accion': 'actualizado', 'chunks_corpus': 6, 'agregados': 1, 'huerfanos': 0, 'podados': 0, 'conteo': 6}
Eventos de la consulta: consulta_recibida → recuperacion_iniciada → recuperacion_finalizada → documento_descartado_por_inyeccion
  → contexto_filtrado → generacion_iniciada → generacion_finalizada → consumo_llm → consulta_finalizada → respuesta_servicio
Respuesta: {"respuesta": "[SIMULADO] Según la documentación: Los clientes pueden devolver un producto dentro de los 30 días
  siguientes a la compra, presentando la boleta y el producto sin uso. [1]", "fuentes": [{"numero": 1, "documento":
  "demo/politica_devoluciones.md"}], "estado": "respondida", "prompt_version": 2, "prompt_huella": "5cbcf92439d0",
  "tokens": {"input_tokens": 506, "output_tokens": 42, "total_tokens": 548}, "medicion": "simulada",
  "costo_estimado_usd": null, "unidades_descartadas": 1, ...}
Abstención: {"estado": "abstencion", "motivo": "contexto_comprometido", "respuesta": "Los fragmentos recuperados se
  descartaron por contener patrones de inyección de prompt; no hay información confiable suficiente para responder.", "fuentes": []}
Supervisión: {'pausado_en': 'solicitar_supervision', 'activa_inicial': '5cbcf92439d0', 'tras_aprobar': 'b3730cbad6b8',
  'tras_rechazar': 'b3730cbad6b8', 'decisiones': 'simuladas'}

Resultado: 11/11 comprobaciones correctas. No se probó el modo REAL.
```

Qué comprueba cada paso:

| Paso | Comprobación |
|---|---|
| 1–2 | 4 documentos sintéticos; colección creada con el conteo igual a los chunks del corpus |
| 3 | Exactamente 1 `embed_query` y 0 `embed_documents` por consulta |
| 4 | 1 unidad descartada (el FAQ cuya inyección solo aparece al expandir la sección) y ausente de las fuentes del contexto |
| 5–6 | Respuesta marcada `[SIMULADO]`, estado `respondida`, única fuente citada `demo/politica_devoluciones.md` |
| 7 | Secuencia de eventos exacta con un único trace_id; el JSONL no contiene el correo sintético `ana.prueba.gate2@ejemplo.cl`, la pregunta, la frase maliciosa ni el contenido del documento |
| 8 | `medicion=simulada`, tokens presentes, costo `null` (sin tarifa: no se inventa) y `prompt_version=2` |
| 9 | Corpus con un único documento malicioso → `abstencion/contexto_comprometido`, sin fuentes y **0 llamadas al modelo** |
| 10 | Segunda corrida: `reutilizado`, el mismo conteo y 0 `embed_documents`; al agregar un documento: `actualizado`, +1 chunk |
| 11 | Grafo real del Bloque 32 sobre una copia del registro: pausa, no se activa antes de aprobar, la aprobación activa v3 y el rechazo conserva v3; `data/gobernanza/registro_prompts.json` queda sin cambios |

## 3. Hallazgos durante la integración

1. **Las citas inválidas solo se registraban:** `consultar_auditado` emitía `citas_invalidas`, pero devolvía el texto. El servicio ahora no entrega respuestas con citas inexistentes ni respuestas factuales sin citas (`rechazada_*`).
2. **Chroma retiene archivos en Windows:** al borrar el directorio temporal se producía `WinError 32`. `cerrar_servicio()` libera `SharedSystemClient.clear_system_cache()` antes de limpiar.
3. **Dependencia sin fijar:** `langgraph` (ver `entrega-gate2.md`, sección 8).
4. **Pregunta mal recuperada en DEMO:** con la pregunta «¿Cómo se reembolsa una devolución?», el FAQ (la fuente pertinente) se descarta por inyección y el modelo simulado repite la garantía. La cita es válida, pero la respuesta no es pertinente. Es una limitación del doble de prueba y de la validación de citas, que comprueba existencia y no respaldo semántico; queda registrada como riesgo residual.

5. **El README es parte del corpus:**
   - La primera validación final dio **1 fallo** en una prueba anterior: `test_rag_metricas_bloque27.py::test_etiquetas_reales_coinciden_con_el_chunking_determinista`.
   - Causa: la sección del Gate 2 se había insertado al principio de `README.md`, que pertenece al corpus del Bloque 24. Eso desplazó los chunks y rompió las etiquetas congeladas del Bloque 27.
   - Corrección: la sección se movió al final, como añadido puro. No se tocaron la prueba ni el dataset.
   - Efecto pendiente: el índice real tiene 23 chunks sin indexar de `README.md` (R04; no se reindexó).

## 4. Revisión final de entrega

### 4.1 Citación y fundamentación

- **Hallazgo 4 resuelto de forma conservadora:**
  - Se agregó `src/rag/fundamentacion.py` (relevancia y respaldo léxicos) a la validación final del servicio.
  - La pregunta sobre reembolsos ahora termina en `abstencion / fuente_no_pertinente` (0 raíces comunes entre la pregunta y `demo/garantia.md`). Es el paso 12 del ensayo: **12/12**.
- **Error propio detectado por una prueba:** al reordenar «. [1]», la primera versión de `oraciones_citadas` fusionaba oraciones. Se corrigió el código, no la prueba.
- **Casos probados en `tests/test_fundamentacion_gate2.py`:**
  - cita inexistente;
  - cita al número que tendría la fuente descartada;
  - contenido de la fuente descartada atribuido a otra cita;
  - pregunta sin información;
  - contradicción numérica y negación contradictoria;
  - fuente irrelevante;
  - **falso negativo conocido:** una paráfrasis falsa con las mismas palabras pasa;
  - **falso positivo conocido:** una respuesta correcta con sinónimos se rechaza.

### 4.2 JSONL real del ensayo (`python -m src.ensayo_gate2 --copiar-log ...`)

- **Volumen:** 30 eventos de 3 trazas (10 eventos por consulta, cada uno con su `trace_id`).
- **Búsqueda negativa:** no aparecen la pregunta del ensayo, el correo `ana.prueba.gate2@ejemplo.cl`, la pregunta de reembolsos, ninguna oración del corpus sintético, ninguna línea del prompt de sistema, `[SIMULADO]`, `<contexto>` ni `AIza`.
- **Textos largos:** los únicos valores de más de 25 caracteres son metadatos: `demo/politica_devoluciones.md`, el nombre del evento y el encabezado de sección `Preguntas frecuentes > Reembolsos de una devolución` del documento descartado.

### 4.3 Preflight del modo REAL (sin llamar a Gemini)

`python -m src.rag.preflight` → 0 errores y 0 advertencias:
- hay una clave configurada (no se verificó su validez ni la cuota);
- modelo de generación `gemini-3.5-flash-lite` (definido en `AI_MODEL` de `.env`) y embeddings `models/gemini-embedding-001`, ambos con tarifa verificada;
- índice `D:\Repositorios\curso\plantilla-base\vectorstore`, colección `corpus_proyecto_bloque24_md` (markdown 200/30): 261 chunks de 8 documentos, todos con `fuente` y embeddings coherentes;
- dataset del Bloque 27 válido y congelado.

`python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md --plan` (solo lectura) → 284 chunks en el corpus, **23 nuevos** (todos de `README.md`), 261 existentes y 0 huérfanos.

**Comandos identificados y NO ejecutados:**

```powershell
# Actualización incremental del índice real: agrega solo los 23 chunks nuevos (23 textos a Gemini embeddings, en lotes de 20 con pausa de 15 s)
.\.venv\Scripts\python.exe -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md
# Una única consulta real del servicio (1 embed_query + 1 generación; preflight automático antes de crear los clientes)
.\.venv\Scripts\python.exe -m src.servicio_rag --real --pregunta "¿Qué agente o herramienta requiere aprobación humana?"
```

## 5. Pruebas

| Comando | Resultado |
|---|---|
| `pytest tests/test_gate2.py -v` | 23 passed |
| `python -m src.rubrica_gate2` | 4 no compensables CUMPLE; promedio 81,75 → `LISTO_PARA_REVISION` (autoevaluación) |
| `pytest tests/ -v` (primera entrega) | 631 passed, 10 warnings (preexistentes); 578 antes del Gate |
| `pytest tests/test_fundamentacion_gate2.py` (revisión final) | 16 passed |
| `python -m src.ensayo_gate2` (revisión final) | 12/12 |
| `pytest tests/ -v` (revisión final) | **647 passed**, 10 warnings (preexistentes) |
| `python -m src.preflight_gate2` (revisión final) | 0 errores, 0 advertencias |
