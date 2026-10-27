# Bloque 13 — Registro de backoff, cuota y costos

> **Estado: pendiente de ejecución real.** Completar únicamente con observaciones propias.

- Fecha: pendiente
- Modelo configurado (`AI_MODEL`): pendiente
- Número de solicitudes ejecutadas: pendiente
- Primer código 429 observado (si ocurrió): pendiente
- Pausas observadas (backoff + jitter): pendiente
- Solicitudes exitosas: pendiente
- Fallos definitivos: pendiente
- Tokens registrados: pendiente
- Costo **referencial** acumulado: pendiente

## Verificación sin consumir cuota

Ejecutar `python -m unittest discover -s tests -p "test_cliente_bloque13.py" -v` y registrar resultado.

## Advertencias

El costo por 1000 tokens del ejemplo es **didáctico**, no corresponde necesariamente a la tarifa vigente de Gemini. El curso pide observar un rate limit real, pero las pruebas simuladas no demuestran que se haya producido un 429 real; documentar por separado ambas evidencias. No compartir `.env` ni la clave.
