# Evidencia del Bloque 18

**Estado:** pendiente de ejecución real y revisión.

- Fecha:
- Modelo (`AI_MODEL`):
- Consulta utilizada:
- Resultado final de la chain:
- Pruebas unitarias (`pytest`):
- Observaciones sobre las tres etapas:
- ¿Hubo errores o límites de cuota?:

La ejecución real usa tres llamadas a Gemini. No rellenar este documento con salidas simuladas.
# Evidencia — Bloque 18: Chain de tres pasos con LangChain

## Objetivo

Construir y ejecutar una cadena de tres pasos conectados mediante LangChain y Gemini, utilizando plantillas de prompts, procesamiento de salidas y pruebas automatizadas.

## Entorno

- Python: 3.13.5
- pytest: 9.2.0
- Modelo: gemini-3.5-flash-lite
- Entorno virtual: `.venv`

## Etapas implementadas

1. Clasificar y analizar una consulta técnica.
2. Redactar una propuesta de solución.
3. Revisar y mejorar la respuesta final.

## Resultados de pruebas automatizadas

- `test_cadena_realiza_tres_pasos_y_produce_respuesta_final`: PASSED
- `test_falta_variable_consulta`: PASSED
- `test_reutilizacion_de_cadena`: PASSED

**Resultado: 3 pruebas aprobadas en 0,90 segundos.**

## Prueba de integración con Gemini

Comando ejecutado:

`python -m src.cadena_tres_pasos`

La ejecución generó una respuesta técnica relacionada con un problema de importación del módulo `dotenv` en Python.

La respuesta incluyó instrucciones para activar el entorno virtual, instalar `python-dotenv`, verificar las dependencias y solicitar información adicional para continuar el diagnóstico.

## Observaciones

Durante la ejecución aparecieron tres advertencias indicando que `gemini-3.5-flash-lite` ignora el parámetro `temperature`.

Estas advertencias no impidieron completar la cadena.

## Conclusión

La cadena de tres pasos se ejecutó correctamente, sus componentes fueron verificados mediante pruebas unitarias y se obtuvo una respuesta real utilizando Gemini.

**Estado: validación técnica satisfactoria.**