# Bloque 21 — Primer agente con herramientas y traza

## Alcance del curso

La actividad del Bloque 21 pide un agente con **al menos dos herramientas propias**, definidas mediante `@tool` y con descripciones claras; construido con `create_tool_calling_agent` y `AgentExecutor`; con `return_intermediate_steps=True`; y **al menos dos invocaciones reales** que permitan confirmar qué herramienta eligió el modelo. Las pruebas automatizadas son una ampliación opcional, no un reemplazo de esas dos ejecuciones reales.

## Dominio elegido

Asistente educativo para tareas de desarrollo Python y Git. A diferencia del ejemplo didáctico de documentación y calculadora, se agregan herramientas orientadas a diagnóstico de errores Python y recomendaciones Git de solo lectura. **No inspeccionan el equipo, no ejecutan comandos y no acceden a Internet**.

- `diagnosticar_error_python(error: str)`: ofrece orientación general sobre `ModuleNotFoundError`, `NameError` y `TypeError`.
- `sugerir_comando_git(operacion: str)`: sugiere `git status`, `git diff` o `git log` según la petición, sin ejecutarlos.

La implementación preserva los Bloques 18–20.

## Instalación

Dentro de `.venv`:

```powershell
python -m pip install langchain-classic
```

Agrega `langchain-classic` a tu `requirements.txt` y, una vez comprobada la versión instalada, considera fijarla para facilitar reproducibilidad. Las dependencias anteriores se conservan.

## Validación

Pruebas offline (no llaman a Gemini):

```powershell
python -m pytest tests/test_agente_con_herramientas.py -v
python -m pytest tests/ -v
```

Ejecución real (sí consume tokens):

```powershell
python -m src.agente_con_herramientas
```

Inspecciona la lista `Herramientas utilizadas` de cada consulta. En las primeras dos se espera que aparezcan `diagnosticar_error_python` y `sugerir_comando_git`, respectivamente. Si el modelo no elige una herramienta esperada, registra la discrepancia; no inventes un resultado exitoso. La tercera consulta es una comprobación adicional: puede responder directamente sin herramientas.

## Precauciones

- Una traza muestra **acciones, argumentos y observaciones**, no pensamientos privados del modelo.
- El uso de herramientas depende de decisiones del modelo, por lo que puede variar entre ejecuciones.
- La traza se imprime para inspección, pero no se almacena automáticamente ni se considera validada antes de ejecutar.
- Los diagnósticos son orientativos y los comandos Git solo sugerencias.
