# Bloque 19 — Enrutamiento condicional según el tipo de entrada

## Objetivo académico

Partiendo del Bloque 18, clasificar mensajes de soporte como `pregunta`, `queja` o `sugerencia`, conservar el mensaje original con `RunnablePassthrough.assign` y seleccionar la respuesta mediante `RunnableBranch`. Cada ruta usa un prompt distinto.

## Archivos propuestos

- `src/enrutamiento.py`: construcción de clasificación, tres rutas, bifurcación y demostración con Gemini.
- `tests/test_enrutamiento.py`: cinco pruebas offline (tres categorías, default y normalización).

Esta estructura `src/` y `tests/` sigue la organización del repositorio existente; el material ofrece como ejemplo `enrutamiento.py` y `test_enrutamiento.py` en la misma carpeta.

## Configuración

En la raíz del repositorio, activar el entorno virtual existente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se reutilizan las dependencias del Bloque 18 (`langchain-core`, `langchain-google-genai`, `python-dotenv` y `pytest`). No agregues nuevas versiones al `requirements.txt` sin comprobar las ya instaladas.

El programa lee `AI_MODEL` y `API_KEY` del `.env` del proyecto, con compatibilidad con `GOOGLE_API_KEY` o `GEMINI_API_KEY`. Nunca subir `.env`.

## Comandos de verificación

```powershell
python -m pytest tests/test_enrutamiento.py -v
python -m pytest tests/ -v
python -m src.enrutamiento
```

Las pruebas no ejecutan llamadas a Gemini. El último comando sí hace **6 llamadas reales**: una clasificación y una respuesta por cada uno de los tres mensajes. El resultado textual puede variar.

## Criterios de cierre

- [ ] La clasificación devuelve las categorías esperadas en ejemplos reales.
- [ ] El flujo conserva la entrada original al agregar `categoria`.
- [ ] La rama `queja` tiene una prueba.
- [ ] La rama `sugerencia` tiene una prueba.
- [ ] La ruta predeterminada `pregunta` tiene pruebas para categoría conocida y desconocida.
- [ ] La normalización está probada.
- [ ] Las tres rutas usan prompts diferentes.
- [ ] Se registra evidencia real de pytest y de una ejecución.
- [ ] Se versiona y publica sin alterar archivos de bloques previos.

## Observaciones

El material usa como ruta predeterminada `pregunta`, incluso ante categorías inesperadas. En una aplicación de producción se podría preferir un manejo explícito para entradas ambiguas, pero ese ajuste es opcional y no es un requisito de este bloque.

Las pruebas usan `MagicMock(return_value=...)`, no `.invoke.return_value`, como explica el material.
