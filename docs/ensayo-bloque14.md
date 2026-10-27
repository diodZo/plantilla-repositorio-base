# Bloque 14 — Registro de pruebas unitarias

**Estado:** pendiente de ejecutar en el repositorio original.

## Objetivo

Verificar, sin llamadas reales a Gemini, las funciones `enviar_peticion`, `con_reintento`, `registrar_costo` y `consultar_modelo` de `src/cliente.py`.

## Comandos

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Resultados del ensayo en el proyecto

- Fecha y hora: **pendiente**
- Versión de Python: **pendiente**
- Commit probado: **pendiente**
- Pruebas completadas: **pendiente**
- Pruebas fallidas: **pendiente**
- Tiempo de ejecución: **pendiente**
- Observaciones y correcciones: **pendiente**

## Alcance

Se utilizan `unittest.mock` y `pytest` para aislar red y temporizadores. Se valida el manejo de estados HTTP, las esperas, la propagación de errores, el costo de sesión y la interfaz pública. La tarifa de costos actual es **referencial**, no la facturación oficial de Gemini. Una suite verde no garantiza disponibilidad de la API real.
