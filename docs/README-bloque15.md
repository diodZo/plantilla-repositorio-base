# Bloque 15 — instalación y evidencia

Este paquete se añade al proyecto sin reemplazar los módulos de los Bloques 12–14.

## Ubicación

- `src/pipeline_texto.py`: `limpiar_texto`, `tokenizar`, `procesar_texto`, `vectorizar` y coincidencia.
- `src/ensayo_bloque15.py`: tres consultas reales a Gemini y registro de resultados.
- `tests/test_pipeline_texto.py`: pruebas unitarias sin conexión a internet.

## Pasos (PowerShell, desde la raíz del proyecto)

```powershell
python -m src.pipeline_texto
python -m pytest tests/test_pipeline_texto.py -v
python -m pytest tests/ -v
```

Para completar la evidencia de la actividad, después de verificar `.env` y la cuota disponible:

```powershell
python -m src.ensayo_bloque15
```

Se creará `docs/ensayo-bloque15.md` con las tres respuestas **reales**, la referencia y los porcentajes antes/después. No rellenes esta evidencia con resultados inventados. Los porcentajes pueden ser bajos incluso si la respuesta es buena: son coincidencias léxicas, no evaluación semántica.

## Git

```powershell
git add src/pipeline_texto.py src/ensayo_bloque15.py tests/test_pipeline_texto.py docs/ensayo-bloque15.md
git commit -m "Agrega pipeline de limpieza y tokenización del Bloque 15"
git push origin main
```

Si decides versionar también este README, copia `docs/README-bloque15.md` e inclúyelo en `git add`.
