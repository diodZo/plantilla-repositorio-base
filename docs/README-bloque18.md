# Bloque 18 — Primera chain de tres pasos

## Objetivo

Crear una chain propia con LangChain para clasificar, redactar y revisar una consulta técnica.
La salida de cada paso es la entrada del siguiente.

## Archivos

- `src/cadena_tres_pasos.py`: tres `PromptTemplate`, `StrOutputParser` y composición con `|`.
- `tests/test_cadena_tres_pasos.py`: pruebas sin llamadas reales a Gemini.
- `docs/ensayo-bloque18.md`: registro para completar después de una ejecución real.

## Instalación

Desde la raíz del proyecto, con `.venv` activado:

```powershell
python -m pip install langchain langchain-google-genai
python -m pip freeze | Select-String 'langchain|google|dotenv'
```

Agrega `langchain` y `langchain-google-genai` a tu `requirements.txt` conservando las otras dependencias. Para un entorno reproducible, fija las versiones realmente instaladas después de comprobar compatibilidad.

El archivo `.env` existente del Gate 1 contiene `API_KEY` y `AI_MODEL`; el ejemplo los reutiliza. Nunca publiques `.env`.

## Prueba sin consumir cuota

```powershell
python -m pytest tests/test_cadena_tres_pasos.py -v
```

## Ejecución real (3 llamadas a Gemini)

```powershell
python -m src.cadena_tres_pasos
```

Pega el resultado real y la fecha en `docs/ensayo-bloque18.md`. No atribuyas al modelo pasos que no ejecutó, ni consideres una prueba simulada como una llamada real.

## Versionamiento

```powershell
git add src/cadena_tres_pasos.py tests/test_cadena_tres_pasos.py docs/README-bloque18.md docs/ensayo-bloque18.md requirements.txt
git commit -m "Agrega chain de tres pasos con LangChain"
git push origin main
```
