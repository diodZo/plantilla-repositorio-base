# Ensayo Bloque 32 — Registro de la implementación

Fecha: 23 de noviembre de 2026 · Python 3.13.5 · langgraph 1.2.19 · sin llamadas a Gemini, sin entrenamiento ni reindexación.

## 1. Punto de partida

El Bloque 31 dejó una limitación documentada: la protección contra la inyección solo existe en `consultar_auditado`. La inspección confirmó, además, que hay **dos prompts reales en uso simultáneo**: v1 (Bloque 26) en las rutas antiguas y v2 (Bloque 31) en la ruta auditada. El historial de git respalda ambas versiones con autor y fecha, así que el ejercicio usó dos versiones reales en vez de inventar una segunda; las propuestas adicionales están marcadas como académicas y solo viven en copias temporales.

## 2. Decisiones de diseño

- **Qué se versiona:** las dos plantillas (sistema y humano) en un texto canónico. Versionar solo el mensaje de sistema habría dejado fuera el aviso de datos no confiables que v2 añadió al mensaje humano.
- **Registro frente a código:** el registro no sustituye el prompt enviado; lo identifica. Activar una versión en el registro no cambia lo que se envía, y la auditoría lo hace visible con `prompt_es_activa`. Se evitó así una sustitución automática sin pruebas en la ruta productiva.
- **Decisión humana:** además de exigir un `bool` estricto, la decisión debe traer la huella revisada y un código de confirmación cuyo hash está en el estado. Esto distingue a quien inició la solicitud de un `Command(resume=True)` arbitrario, pero **no es autenticación**.

## 3. Hallazgos durante el desarrollo

1. **Reanudar un hilo resuelto no falla en LangGraph**: devuelve el estado final. Sin la comprobación previa con `get_state`, una «segunda aprobación» parecería exitosa.
2. **Un valor de reanudación inválido envenena el hilo** si el nodo lanza una excepción: LangGraph lo conserva y lo reutiliza. Se rediseñó el nodo para registrar el error y volver a interrumpir; la prueba `test_codigo_incorrecto_no_aprueba_ni_envenena_el_hilo` verifica que después una decisión válida sí funciona.
3. **Todos los riesgos quedaron al límite.** Con estimaciones entre 4 y 12, cualquier ±1 cruza un corte oficial. No se movieron los cortes; se documentó la fragilidad.
4. **Brecha de la inyección:** el criterio académico pide detener y derivar a revisión; el sistema actual descarta y continúa. Se registró como control propuesto, no como mitigación completa.

## 4. Resultados

- Registro: v1 `10915cb400b1` (reemplazada) y v2 `5cbcf92439d0` (activa). El diff v1→v2 es exactamente la regla 8 más una línea de aviso.
- Supervisión:
  - Aprobación simulada: v3 se activa **solo después** de la decisión. Antes, el grafo está en `('solicitar_supervision',)` y la propuesta en `propuesta`.
  - Rechazo simulado: la versión activa no cambia.
  - `aprobado='no'` y `Command(resume=True)` no aprueban.
  - Tras un reinicio, la solicitud queda huérfana y no se activa nada.
- Matriz: 8 riesgos, 4 ALTO y 4 MEDIO. Los 4 ALTO tienen control humano identificado: R06 implementado y probado, R04 documentado pendiente, R02 y R03 propuestos.
- Integración: cada consulta auditada registra versión y huella del prompt realmente enviado, con su `trace_id`.
- Pruebas: **578 passed** (451 + 127), con las mismas 10 advertencias previas.

## 5. Conclusión

Las tres piezas funcionan y son reproducibles sin red. La gobernanza agregada es real pero parcial: protege el registro de versiones y deja evidencia auditable del prompt usado. Sin embargo, el texto efectivo sigue viviendo en el código, no hay autenticación de aprobadores y varios controles humanos de la matriz siguen propuestos.
