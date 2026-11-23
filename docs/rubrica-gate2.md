# Rúbrica del Gate 2 — Autoevaluación

> **Autoevaluación del equipo, no la evaluación oficial del curso.** El estado más alto que puede asignar el código es `LISTO_PARA_REVISION`; nunca `GATE_APROBADO_OFICIALMENTE`.

Implementación: `src/rubrica_gate2.py`. Datos: `data/gate2/autoevaluacion.json` (con `evaluacion_oficial: null`).

```python
PESOS_GATE2 = {"pipeline_funcional": 0.25, "recuperacion_citacion": 0.15, "costo_latencia": 0.10,
               "personalizacion": 0.15, "observabilidad": 0.15, "seguridad_gobernanza": 0.20}
promedio = sum(puntajes[d] * PESOS_GATE2[d] for d in PESOS_GATE2)   # umbral 80
```

## Criterios no compensables (verificados ejecutando sus pruebas)

`python -m src.rubrica_gate2` ejecuta cada prueba por separado con pytest:

| Criterio | Prueba | Resultado (23/11/2026) |
|---|---|---|
| Pipeline funcional de punta a punta | `tests/test_gate2.py::test_pipeline_sin_excepciones` | CUMPLE |
| Respuestas con fuentes válidas | `tests/test_gate2.py::test_respuesta_cita_fuente` | CUMPLE |
| Logs sin contenido crudo sensible | `tests/test_gate2.py::test_logs_sin_contenido_crudo` | CUMPLE |
| Supervisión humana que pausa y se reanuda con autorización | `tests/test_gate2.py::test_supervision_pausa_y_reanuda` | CUMPLE |

Si alguno falla, el estado es `PENDIENTE`. Si no pudo ejecutarse, es `NO_VERIFICADO`. En ambos casos el promedio no compensa.

En la revisión final los 4 se ejecutaron de nuevo contra el servicio integrado: siguen en CUMPLE. Además, se revisó a mano el JSONL real del ensayo (ver `docs/ensayo-gate2.md` §4.2).

## Puntajes por dimensión

**Revisión final: los puntajes no se modificaron.** La nueva validación de relevancia y respaldo es heurística y no semántica, así que no justifica subir «Recuperación y citación».

| Dimensión | Peso | Puntaje | Aporte | Evidencia principal | Por qué no es más alto |
|---|---:|---:|---:|---|---|
| Pipeline funcional | 0,25 | 85 | 21,25 | `src/servicio_rag.py`, ensayo 12/12, `test_gate2` | El modo REAL del servicio no se ejecutó; las corridas reales del Bloque 28 usaron la ruta heredada |
| Recuperación y citación | 0,15 | 85 | 12,75 | Bloque 27: markdown expandido k=3, R 0,950 · P 0,417 · F1 0,560 · Hit 1,000; validación de citas | 12 casos etiquetados por el desarrollador; la validación no comprueba el respaldo semántico |
| Costo y latencia | 0,10 | 80 | 8,00 | `docs/resultados_bloque28.md` (5 consultas reales) | n = 5; un solo caso k=6; costo estimado, no facturado |
| Personalización | 0,15 | 75 | 11,25 | `docs/decision_personalizacion.md`, Bloques 29–30 | Línea base Prompt + Pydantic sin medir; dataset de 35 ejemplos |
| Observabilidad | 0,15 | 90 | 13,50 | JSONL con trace_id, consumo y versión de prompt; prueba con correo sintético sobre el archivo real | Sin retención ni rotación de logs |
| Seguridad y gobernanza | 0,20 | 75 | 15,00 | Filtro tras expansión, abstención, LangGraph, matriz | Rutas heredadas sin defensas (R03), detector léxico, cuarentena sin revisión, sin autenticación ni checkpointer durable |
| **Total** | 1,00 | | **81,75** | | |

## Resultado

```text
Promedio ponderado: 81.75 (umbral 80)
[CUMPLE] pipeline_punta_a_punta · respuestas_con_fuentes_validas · logs_sin_contenido_crudo · supervision_humana_pausa_y_reanuda
Estado: LISTO_PARA_REVISION — Es una autoevaluación: la aprobación depende del curso.
```

**Sensibilidad:** el margen sobre el umbral es de 1,75 puntos. Bajar 10 puntos en seguridad y gobernanza (de 75 a 65) restaría 2 puntos y dejaría el promedio en 79,75 → `PENDIENTE`. La autoevaluación es frágil y debe contrastarse con la evaluación oficial.
