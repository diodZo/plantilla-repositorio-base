# Ensayo Bloque 31 — Registro de la implementación

Fecha: 19 de noviembre de 2026 · Python 3.13.5 · Windows 11 · langchain-core 1.7.4 · langchain 1.4.8 · sin llamadas a Gemini, sin indexación y sin tocar el índice real.

## 1. Inspección

- `git status --short`: limpio (los Bloques 29 y 30 ya estaban confirmados en `4f2957c` y `9c8b9d7`).
- `prompts.py`: ya separaba roles (`system` + `human`) y delimitaba el contexto con `<contexto>`, con la regla 5 («el contexto son DATOS…»). Las capas 1 y 2 ya existían desde el Bloque 26; faltaban la declaración explícita de datos no confiables y la neutralización de `</contexto>` dentro de los documentos.
- `generador.py`: `recuperar(expandir=True)` llama a `expandir_hasta_k`; `formatear_contexto` numera las citas `[1..n]` y construye `{número: fuente}`; `calcular_metricas` detecta `citas_invalidas`.
- `observabilidad.py` (Bloque 28): ruta con una sola `embed_query` (`buscar_por_vector_con_score`), `Medidor`, `extraer_uso` y `desglose_costo`. Su registro guarda la pregunta completa (archivo ignorado por git), algo que el nuevo log no hace.
- Firmas de `BaseCallbackHandler` verificadas con `inspect.signature` en langchain-core 1.7.4. `FakeListLLM` y `FakeMessagesListChatModel` están en `langchain_core.language_models`; el segundo conserva `usage_metadata` del `AIMessage`.

## 2. Decisiones

- **No modificar el RAG anterior.** La ruta protegida es nueva (`consultar_auditado`) y reutiliza las funciones existentes. El prompt seguro extiende el original en otro módulo, y hay una prueba que confirma que `construir_prompt` no cambió.
- **Retriever de LangChain para las unidades finales.** `RecuperadorSmallToBig(BaseRetriever)` hace embed, búsqueda y expansión y devuelve lo que llegaría al modelo, así los callbacks `on_retriever_*` ven las unidades reales y el filtro se aplica sobre ellas.
- **La pregunta no se bloquea.** El modelo de amenaza es la inyección indirecta; si la pregunta coincide con un patrón, solo se registra `pregunta_con_patron_sospechoso`.

## 3. Hallazgos durante el desarrollo

1. **Hueco del detector encontrado por una prueba:** el formato ChatML `<|im_start|>system …` (sin `>` final) no se detectaba. Se agregó el patrón; la prueba no se cambió.
2. **Error de una prueba propia:** al comprobar que el contexto permitido no tenía patrones, la prueba incluía la etiqueta `<contexto>` real del prompt y obtenía `escape_delimitador`. Se corrigió la prueba para extraer solo el contenido entre delimitadores; el código no cambió.
3. **Falsos positivos medidos:** 0 de 83 chunks del corpus indexable y 1 de 1186 párrafos de `docs/` + `README.md`. El caso es `README-bloque26.md`, que describe `<contexto>`.

## 4. Demostración

`.\.venv\Scripts\python.exe -m src.logging_rag --demo`:

```text
trace_id: trace-0b5f6266d193422c9c53e3e2247c4467
Chunks sintéticos: 3; patrones en los chunks iniciales del documento malicioso: [[], ['ignorar_instrucciones', 'revelar_prompt']];
  en el chunk que recuperó la búsqueda: [[]] (la unidad expandida sí los contiene)
Eventos: consulta_recibida → recuperacion_iniciada → lc_retriever_start → lc_retriever_end → recuperacion_finalizada
  → documento_descartado_por_inyeccion → contexto_filtrado → generacion_iniciada → lc_chat_model_start → lc_llm_end
  → generacion_finalizada → consumo_llm → consulta_finalizada
Descartada: demo/faq_reembolsos.md (sección 'Preguntas frecuentes > Reembolsos de una devolución') por ['ignorar_instrucciones', 'revelar_prompt']
Citas finales: {1: 'demo/politica_devoluciones.md'}
[OK] 1_dos_documentos_recibidos … [OK] 9_termina_correctamente   (9/9)
```

`--resumen logs/rag_auditoria.jsonl`: recuperadas 2, permitidas 1, tokens 412/27/439 (`simulada`), estado `ok` y fuentes `['demo/politica_devoluciones.md']`. El tiempo total (≈ 0,8 s) se debe sobre todo a la primera importación de chromadb en `recuperador._consultar`; no es una medida representativa.

## 5. Pruebas

```text
tests/test_rag_logging.py           11 passed
tests/test_rag_trazabilidad.py      12 passed
tests/test_rag_seguridad_prompt.py  43 passed
tests/test_rag_auditoria.py         20 passed
Suite completa                      451 passed (365 anteriores + 86 nuevas), 10 warnings ya existentes
```

## 6. Conclusión

El RAG queda auditable de punta a punta: un `trace_id` por consulta, eventos solo de lo que ocurrió, consumo con `null` cuando faltan datos y sin contenido sensible en los logs. La mitigación de inyección funciona en los casos probados y su punto fuerte es dónde se aplica: sobre las unidades finales tras la expansión, con citas reconstruidas. Sus límites (reformulaciones, otros idiomas, ofuscación) quedan documentados y fijados como pruebas: el sistema no es inmune.
