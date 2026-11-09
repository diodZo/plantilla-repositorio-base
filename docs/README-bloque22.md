# Bloque 22 — Herramienta personalizada y memoria entre interacciones

> El documento oficial `bloque 22.md` no estaba disponible en el repositorio local. Esta implementación sigue los requisitos del enunciado de la tarea: herramienta con `args_schema` Pydantic, agente con `create_tool_calling_agent` + `AgentExecutor`, y memoria por `session_id`.

## Arquitectura

```
entrada + session_id
        │
RunnableWithMessageHistory ── AlmacenSesiones.obtener_historial(session_id)
        │   (inyecta chat_history / guarda entrada y output)
        ▼
AgentExecutor (create_tool_calling_agent, return_intermediate_steps=True)
        │   prompt: system → chat_history → human → agent_scratchpad
        ▼
RunnableLambda(normalizar_resultado_agente)   ← output: lista de bloques → str
        │
        ▼
{"output": str, "intermediate_steps": [...], ...}  → historial + llamador
```

Responsabilidades separadas en `src/agente_bloque22.py`:

| Pieza | Función |
|---|---|
| `ArgumentosDiagnosticoPython` + `diagnosticar_error_python_detallado` | Lógica y validación de la herramienta |
| `construir_prompt` / `construir_ejecutor(modelo)` | Construcción del agente (el modelo se inyecta) |
| `AlmacenSesiones` | Historiales en RAM por `session_id` |
| `texto_salida` / `normalizar_resultado_agente` | Convertir la salida de Gemini a texto apto para el historial |
| `construir_agente_con_memoria(ejecutor, almacen)` | Composición final (ejecutor y almacén inyectados) |

## Herramientas disponibles

1. `diagnosticar_error_python_detallado` (nueva, Bloque 22): orienta sobre `ModuleNotFoundError`, `NameError` y `TypeError`.
2. `sugerir_comando_git` (reutilizada del Bloque 21): solo **sugiere** comandos Git de consulta.

Ninguna herramienta ejecuta código, comandos Git ni modifica archivos.

## Esquema Pydantic

| Campo | Tipo | Por defecto | Validación |
|---|---|---|---|
| `error` | `str` | obligatorio | `min_length=1`; se eliminan espacios antes de validar (`"   "` se rechaza) |
| `contexto` | `str` | `""` | Si no está vacío, se añade a la respuesta |
| `incluir_pasos` | `bool` | `False` | Si es `True`, se añaden comprobaciones; `"talvez"` se rechaza |

Cada campo tiene `Field(description=...)`, que es lo que el modelo ve en el esquema de la herramienta. Los argumentos inválidos producen `pydantic.ValidationError`.

## Memoria conversacional

- `RunnableWithMessageHistory` usa `input_messages_key="entrada"`, `history_messages_key="chat_history"` y `output_messages_key="output"`.
- El prompt coloca `chat_history` antes del mensaje humano y `agent_scratchpad` al final (el scratchpad pertenece solo al turno en curso y no se guarda).
- Cada turno agrega 2 mensajes (`HumanMessage` + `AIMessage`).
- Falta de `session_id` → `ValueError` (lo lanza `RunnableWithMessageHistory`). `session_id` vacío o solo espacios → `ValueError` (lo lanza `AlmacenSesiones`).
- `AlmacenSesiones.cerrar_sesion(id)` elimina el historial; cerrar una sesión inexistente no falla.

## Manejo de respuestas estructuradas de Gemini (causa del fallo del segundo turno)

Gemini puede devolver `AIMessage.content` como lista de bloques:

```python
[{"type": "text", "text": "...", "index": 0, "extras": {"signature": "..."}}]
```

`AgentExecutor` copia ese contenido en `output`. Dentro de `RunnableWithMessageHistory._get_output_messages` (langchain-core 1.7.4), un `output` de tipo `list` se interpreta como **una lista de mensajes ya construidos** y se guarda sin convertir. El primer turno parecía correcto (2 elementos en el historial), pero el segundo elemento era un dict de bloque, no un mensaje. En el turno siguiente, `MessagesPlaceholder("chat_history")` intentaba convertirlo y fallaba con:

```
ValueError: Message dict must contain 'role' and 'content' keys  (MESSAGE_COERCION_FAILURE)
```

Corrección: `normalizar_resultado_agente` se ejecuta **dentro** del runnable que envuelve la memoria (`ejecutor | RunnableLambda(normalizar_resultado_agente)`), por lo que el historial siempre recibe un `str`:

- `str` → se conserva.
- Lista de bloques → se unen los bloques `type="text"` y se descartan los demás (firmas, razonamiento).
- Vacío (`""`, `[]`, `None`, solo espacios) → `RESPUESTA_VACIA`, para no guardar un `AIMessage` sin contenido.
- `intermediate_steps` y las demás claves se conservan sin cambios; la entrada no se modifica.
- Un resultado que no es `dict` → `TypeError` explícito.

## Aislamiento de sesiones

Cada `session_id` tiene su propio `InMemoryChatMessageHistory`. Las pruebas comprueban que la sesión `b` no recibe nada de la sesión `a`. El `session_id` **no autentica**: en producción debe asignarlo un servicio que controle el acceso.

## Pruebas offline

```powershell
python -m pytest tests/test_agente_bloque22.py -v
python -m pytest tests/ -v
```

Incluyen:

- Validación del esquema, uso de parámetros opcionales y rechazo de entradas inválidas.
- Normalización (str, bloques, vacíos, bloques no textuales) y conservación de `intermediate_steps`.
- Memoria: dos turnos, aislamiento, cierre de sesión, `session_id` ausente o vacío y respuesta vacía.
- **Regresión** `test_regresion_salida_estructurada_gemini_dos_turnos`: un agente falso devuelve el formato exacto de Gemini y formatea el prompt real, que es donde ocurría el fallo.
- **Integración** `test_agent_executor_real_con_salida_gemini_y_herramienta`: `create_tool_calling_agent` y `AgentExecutor` reales, con un modelo de chat falso (sin red) que primero llama a la herramienta y después responde con bloques de Gemini.

Se comprobó que ambas pruebas críticas **fallan** si se desactiva la normalización. Las pruebas offline no sustituyen la ejecución real: no evalúan qué herramienta elige Gemini.

## Ejecución real con Gemini

```powershell
python -m src.agente_bloque22
```

Requiere `GOOGLE_API_KEY`, `GEMINI_API_KEY` o `API_KEY` en `.env` (opcional: `AI_MODEL`). Consume cuota. Ejecuta 4 consultas: dos en `desarrollador_1` (continuidad) y dos en `desarrollador_2` (aislamiento y herramienta Git). La elección de herramientas es probabilística; revisar `Herramientas` y `Mensajes en historial`.

## Dependencias

`langchain-classic==1.0.8` se añadió a `requirements.txt`: los Bloques 21 y 22 lo importan, ya estaba instalado en `.venv` y no es dependencia transitiva de `langchain==1.4.8`. No se cambió ninguna otra versión.

## Advertencias de deprecación (langchain-core 1.7.4)

- `RunnableWithMessageHistory is deprecated. Use LangGraph's built-in persistence instead.`
- `InMemoryChatMessageHistory` deprecada desde 1.6.4; **se eliminará en 2.0.0**.
- `AgentExecutor` / `create_tool_calling_agent` provienen de `langchain_classic` (API heredada).

Se mantienen por fidelidad al material del curso. Impacto: actualizar a `langchain-core` 2.x romperá este bloque; la migración recomendada es `langchain.agents.create_agent` con un checkpointer de LangGraph (`thread_id` en lugar de `session_id`). Fijar las versiones de `requirements.txt` evita la ruptura mientras tanto.

## Límites

- La memoria está en RAM y desaparece al cerrar el proceso; no hay persistencia (no la exige este bloque).
- El historial crece sin límite: cada turno aumenta los tokens enviados. No hay recorte ni resumen.
- `AlmacenSesiones` no es seguro entre hilos ni procesos.
- Solo se guarda el texto final: las llamadas a herramientas de turnos anteriores **no** quedan en el historial (siguen disponibles en `intermediate_steps` del resultado de cada turno).
- Si el modelo envía argumentos inválidos a la herramienta, la `ValidationError` se propaga y el turno falla (no se configuró `handle_validation_error`).
- El agente solo orienta: no ejecuta comandos ni inspecciona repositorios.
