# Bloque 20 — Manejo de errores por paso en el flujo orquestado

Implementación sobre `src/enrutamiento.py` existente (Bloque 19). El objetivo es preservar las tres rutas y agregar protección ante fallos.

## Cambios

- `construir_cadena_queja_segura(cadena_queja)`: protege la ruta de queja mediante `with_fallbacks` y una respuesta fija apropiada.
- `procesar_mensaje_seguro(cadena, mensaje)`: invoca el flujo y captura fallos no cubiertos, con `logger.exception` para conservar el traceback sin mostrar detalles técnicos al usuario.
- `construir_cadena(modelo)`: ensambla las rutas conservando la inyección del modelo y aplica el fallback a la de queja.
- `main()`: utiliza la entrada protegida y mantiene las variables `API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY` y `AI_MODEL` existentes.

## Probar sin consumir tokens

```powershell
python -m pytest tests/test_enrutamiento.py tests/test_orquestacion.py -v
```

Luego revisar la suite completa:

```powershell
python -m pytest tests/ -v
```

## Ejecutar integración real

```powershell
python -m src.enrutamiento
```

Esta ejecución invoca Gemini. Guardar los resultados en `docs/ensayo-bloque20.md`, sin publicar credenciales ni trazas sensibles.

## Checklist oficial del bloque

- Normalización de clasificación y manejo de entrada ambigua.
- Prueba de cada ruta y de la ruta por defecto.
- Prompts distintos por ruta y protección mediante fallback o captura general.
- Fallos simulados en una ruta y en clasificación con respuesta inteligible.
- Registro de errores recuperados por captura general.

## Notas

- La ruta `pregunta` se conserva como predeterminada, igual que el Bloque 19.
- Las respuestas fijas de respaldo **no** significan que un equipo humano haya recibido o procesado el mensaje.
- `with_fallbacks` actúa ante excepciones, no ante llamadas que quedan bloqueadas sin tiempo límite. Configurar timeouts según la necesidad del entorno.
- `logger.exception` puede imprimir información de la excepción; evitar registrar textos o secretos sensibles.
