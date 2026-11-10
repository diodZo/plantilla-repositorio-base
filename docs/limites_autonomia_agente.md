# Límites de autonomía — Agente educativo Python/Git (Bloque 23)

## Herramientas y riesgo

| Herramienta | Riesgo | Justificación |
|---|---|---|
| `diagnosticar_error_python_detallado` | Bajo (lectura/orientación) | Solo explica errores; no ejecuta programas ni instala paquetes |
| `sugerir_comando_git` | Bajo (lectura/orientación) | Propone comandos informativos sin ejecutarlos ni modificar archivos |
| `reembolso_simulado_con_aprobacion` | Alto **por la naturaleza de la acción que representa**; impacto real nulo en la implementación | Imita el flujo de una operación financiera irreversible; no mueve dinero |

## Supervisión humana

Las dos herramientas de orientación no requieren aprobación. La simulación de reembolso sí pide una decisión humana explícita `s`; cualquier otra respuesta, la falta de consola o el agotamiento del tiempo la bloquea. El resultado de la decisión queda en una lista en memoria con marca de tiempo UTC y argumentos. Esta aprobación no representa autorización para una transacción verdadera y no debe usarse como seguridad de producción.

## Revisión de trazas

`registrar_traza` guarda la consulta, herramienta, argumentos, observación y respuesta final en `trazas_agente_bloque23.jsonl`. `detectar_repeticiones` marca el uso consecutivo repetido de una herramienta. Revisar una muestra semanal de trazas y **todas** las interacciones con herramienta de riesgo alto; contrastar cada una con su registro de aprobación/rechazo.

No guardar conversaciones con datos personales, credenciales o información sensible en este archivo de demostración. Excluir el JSONL de control de versiones.

## Procedimiento ante conducta inesperada

1. Suspender el acceso del agente a la herramienta afectada y dejar de aceptar acciones de riesgo alto.
2. Conservar, con acceso controlado, la traza observable y el registro de aprobación de la incidencia.
3. Reproducir con una prueba offline utilizando entradas anonimizadas y el mismo orden de llamadas.
4. Revisar descripción de herramienta, validaciones, prompt y datos retornados; corregir la causa.
5. Ejecutar pruebas de regresión y reactivar solo tras aprobación del responsable.

## Límites conocidos

- Las decisiones de aprobación viven únicamente durante el proceso y no identifican al supervisor real.
- El log JSONL de trazas persiste en el disco local; no está protegido con permisos, cifrado ni política de retención por esta práctica.
- La simulación no invoca servicios financieros reales y, por tanto, no prueba seguridad de una integración de pagos real.
- La memoria de conversaciones del Bloque 22 continúa siendo efímera; este bloque no la hace persistente.

## Evidencia de ejecución

**Pendiente de consignar los resultados observados en el entorno local.** No se afirma que se hayan ejecutado las pruebas o las llamadas a Gemini.
