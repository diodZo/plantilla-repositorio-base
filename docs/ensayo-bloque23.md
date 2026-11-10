# Evidencia — Bloque 23

**Estado:** pendiente de ejecución en el entorno local. No se inventan resultados.

## Objetivos

- Clasificar las herramientas del agente según riesgo y exigir aprobación en la simulación de acción de riesgo alto.
- Registrar decisiones humanas de aprobación o rechazo.
- Guardar trazas observables en JSONL y señalar repeticiones consecutivas.
- Documentar límites reales, mecanismos y acciones ante conductas inesperadas.

## Comandos y resultados por completar

| Comando | Resultado observado |
|---|---|
| `python -m pytest tests/test_agente_bloque23.py -v` | PENDIENTE |
| `python -m pytest tests/ -v` | PENDIENTE |
| `python -m src.agente_bloque23` | PENDIENTE (Gemini real) |
| `python -m src.agente_bloque23 --demo-aprobacion` | PENDIENTE (simulación, sin Gemini) |

## Validaciones manuales

- [ ] Responder `n`: registrar rechazo y confirmar que no ocurre ninguna operación real.
- [ ] Responder `s`: registrar aprobación y confirmar que **solo se simula** el reembolso.
- [ ] Comprobar que existe `trazas_agente_bloque23.jsonl` tras ejecución de Gemini (sin datos sensibles).
- [ ] Comprobar que se documentaron las tres herramientas y el plan de respuesta ante incidentes.

## Conclusión

PENDIENTE: completar solo con salidas efectivamente observadas.
