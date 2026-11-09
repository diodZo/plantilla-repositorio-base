# Evidencia — Bloque 22: Herramienta personalizada y memoria

## Objetivo

Integrar una herramienta con parámetros validados por Pydantic y memoria de conversación separada por `session_id` en un agente LangChain.

## Incidente observado y diagnóstico

- Ejecución real inicial: el primer turno funcionaba; el segundo fallaba con `ValueError: Message dict must contain 'role' and 'content' keys` (`MESSAGE_COERCION_FAILURE`).
- Causa raíz: Gemini devolvió `output` como lista de bloques (`{"type": "text", ...}`). `RunnableWithMessageHistory` trata una lista en `output` como lista de mensajes y guardó el bloque tal cual en el historial; `MessagesPlaceholder` no pudo convertirlo en el turno siguiente.
- Reproducido de forma offline (sin Gemini) con el prompt real y una salida simulada: mismo `ValueError` en el segundo turno.
- Errores secundarios (`NameError` de `RunnableLambda` y de `normalizar_resultado_agente`): `normalizar_resultado_agente` estaba definida en el archivo de pruebas y no en `src`; había imports duplicados.
- Por qué la suite original no lo detectaba: el agente falso devolvía `output` como `str`, nunca con el formato de lista de Gemini.

## Entorno

Python 3.13.5 · langchain 1.4.8 · langchain-core 1.7.4 · langchain-classic 1.0.8 · langchain-google-genai 4.4.2 · pydantic 2.14.2.

## Resultados observados (2026-11-09)

| Comando | Resultado |
|---|---|
| `python -m pytest tests/test_agente_bloque22.py -v` | 27 passed, 10 warnings |
| `python -m pytest tests/ -v` | 95 passed, 10 warnings |
| Pruebas críticas con la normalización desactivada (monkeypatch) | 2 failed (confirma que detectan el fallo) |
| `python -m src.agente_bloque22` (Gemini real, 2 ejecuciones) | Ambas terminaron con código 0, sin excepciones |

Las 10 advertencias son `LangChainDeprecationWarning` (`RunnableWithMessageHistory` e `InMemoryChatMessageHistory`).

Traza de la ejecución real (la segunda ejecución; la elección de herramientas puede variar entre ejecuciones):

| Sesión | Pregunta | Herramientas | Mensajes en historial |
|---|---|---|---|
| desarrollador_1 | ModuleNotFoundError al importar dotenv | `diagnosticar_error_python_detallado` | 2 |
| desarrollador_1 | ¿Y qué pasos… para ese mismo error? | `diagnosticar_error_python_detallado` | 4 |
| desarrollador_2 | ¿Qué error de Python mencioné antes? | ninguna | 2 |
| desarrollador_2 | ¿Qué comando Git muestra los cambios pendientes? | `sugerir_comando_git` | 4 |

- Continuidad: la respuesta del segundo turno de `desarrollador_1` se refiere a `dotenv` aunque la pregunta no lo nombra.
- Aislamiento: `desarrollador_2` respondió que no tenía registro de errores anteriores.

## Checklist

- [x] La herramienta estructurada documenta y valida sus parámetros.
- [x] La opción `incluir_pasos` cambia la respuesta de la herramienta.
- [x] El prompt contiene el historial antes del mensaje actual.
- [x] El agente conserva el historial de turnos con el mismo `session_id` (offline y con Gemini).
- [x] Las sesiones distintas permanecen aisladas (offline y con Gemini).
- [x] Se identificaron las herramientas realmente seleccionadas (`intermediate_steps`).
- [x] Se preservaron las pruebas de los bloques anteriores (ninguna eliminada; suite completa aprobada).

## Conclusión

La salida estructurada de Gemini se normaliza a texto antes de llegar a la memoria, conservando `intermediate_steps`. La conversación de dos turnos funciona en las pruebas offline y en la ejecución real observada. Queda pendiente la migración futura por las deprecaciones de LangChain (ver `README-bloque22.md`).
