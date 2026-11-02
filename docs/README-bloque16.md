# Bloque 16 — Cálculo de métricas sobre respuestas reales

Este paquete se adapta al repositorio `plantilla-repositorio-base`: las importaciones apuntan a `src.cliente` y `src.pipeline_texto`.

## Instalación

Copiar `src/` y `tests/` a la raíz del proyecto sin borrar archivos anteriores. El archivo `requirements.txt` no cambia porque `Counter`, `json` y `argparse` son estándar; pytest ya estaba instalado en el Bloque 14.

## Verificación sin consumo de Gemini

```powershell
python -m src.metricas_texto
python -m pytest tests/test_metricas_texto.py -v
python -m pytest tests/ -v
```

## Ensayo real (consume cuota)

Para comenzar con 3 consultas y guardar cada resultado exitoso:

```powershell
python -m src.ensayo_bloque16 --cantidad 3
```

Para completar las 20 consultas exigidas en el Bloque 17:

```powershell
python -m src.ensayo_bloque16 --cantidad 20
```

Es seguro reejecutar: las preguntas registradas se omiten y el programa guarda cada respuesta exitosa en `docs/resultados_metricas.json` antes de consultar la siguiente. Si Gemini agota la cuota, puedes reanudar el proceso sin volver a pagar por las respuestas ya registradas. Las métricas se calculan usando referencias preparadas de antemano, que conviene revisar por exactitud factual.

El archivo `docs/resultados_metricas.json` contiene un arreglo de registros con `consulta`, `referencia`, `respuesta`, `precision`, `cobertura`, `f1` y `fecha_utc`.

Una vez reunidos 20 resultados, el Bloque 17 podrá leer el archivo usando:

```powershell
python -m src.preparar_revision_bloque17 --entrada docs/resultados_metricas.json
```

El archivo JSON no viene precargado con datos inventados: se crea al ejecutar consultas reales.

## Entrega

```powershell
git add src/metricas_texto.py src/ensayo_bloque16.py tests/test_metricas_texto.py docs/README-bloque16.md docs/resultados_metricas.json
git commit -m "Implementa métricas de precisión cobertura y F1 del Bloque 16"
git push origin main
```

No hagas `git add` de `docs/resultados_metricas.json` hasta que exista. Evalúa si las respuestas almacenadas contienen información sensible antes de subirlas a un repositorio público.
