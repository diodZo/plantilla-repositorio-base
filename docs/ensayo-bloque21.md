# Evidencia — Bloque 21: Primer agente con herramientas y traza de decisión

## Objetivo

Implementar un agente con LangChain y Gemini capaz de seleccionar dinámicamente herramientas según una consulta y verificar sus decisiones mediante `intermediate_steps`.

## Implementación

Se desarrolló un agente de asistencia al desarrollador con dos herramientas propias:

1. `diagnosticar_error_python`: orientación para diagnosticar errores comunes de Python.
2. `sugerir_comando_git`: recomendaciones de comandos Git de consulta, sin ejecutar modificaciones.

El agente utiliza `AgentExecutor` y registra las herramientas elegidas durante su ejecución.

## Pruebas automatizadas

**Comando:** `python -m pytest tests/test_agente_con_herramientas.py -v`

**Resultado: 7 pruebas aprobadas en 1,32 segundos.**

## Pruebas de regresión

**Comando:** `python -m pytest tests/ -v`

**Resultado: 68 pruebas aprobadas en 1,52 segundos.**

No se observaron pruebas fallidas.

## Ejecución real con Gemini

**Comando:** `python -m src.agente_con_herramientas`

### Caso 1 — Diagnóstico Python

Consulta: «Al ejecutar Python obtengo ModuleNotFoundError. ¿Qué reviso?»

Herramienta seleccionada: `diagnosticar_error_python`.

Resultado: el agente explicó posibles causas y propuso verificaciones del entorno de ejecución.

### Caso 2 — Consulta Git

Consulta: «¿Qué comando Git puedo usar para ver el estado de mi repositorio?»

Herramienta seleccionada: `sugerir_comando_git`.

Resultado: el agente recomendó `git status` y `git status --short`.

### Caso 3 — Pregunta general

Consulta: «¿Qué es una función en programación?»

Herramientas utilizadas: ninguna (`[]`).

Resultado: el agente respondió directamente con una definición y un ejemplo.

## Observaciones

- Las herramientas fueron seleccionadas de acuerdo con las consultas.
- La ejecución real confirmó que el agente puede responder sin invocar herramientas.
- Las decisiones se verificaron mediante las trazas registradas.
- Las pruebas automatizadas no requirieron llamadas a la API.
- La respuesta final se mostró como bloques de contenido estructurado, lo que permite una mejora posterior de presentación.

## Conclusión

El agente cumplió satisfactoriamente los objetivos técnicos verificados del Bloque 21: incorpora al menos dos herramientas diferenciadas, permite inspeccionar las decisiones mediante trazas y seleccionó correctamente las herramientas en las ejecuciones observadas.

**Estado: validación técnica satisfactoria, pendiente de confirmar publicación en GitHub.**