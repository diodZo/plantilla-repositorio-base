# Ensayo Bloque 30 — Registro de la decisión

Fecha: 18 de noviembre de 2026 · Python 3.13.5 · google-genai 2.34.0 · pydantic 2.14.2 · sin llamadas a la API.

## 0. Corrección de los pesos

La primera versión usaba pesos reconstruidos (1 punto por criterio), porque el PDF del Bloque 30 no estaba en el repositorio. Al revisarla se detectó la discrepancia con el material oficial y se reemplazó la tabla `PESOS` por la del curso:

| Criterio | RAG | FT completo | PEFT |
|---|---:|---:|---:|
| `informacion_cambia_seguido` | 3 | 0 | 0 |
| `problema_de_formato_o_tono` | 0 | 1 | 2 |
| `dataset_grande_y_de_calidad` | 0 | 2 | 1 |
| `presupuesto_limitado_o_iterar_rapido` | 2 | 0 | 1 |
| `necesita_multiples_variantes` | 0 | 0 | 2 |

No se cambió la regla de puntuación: suma de pesos de los criterios verdaderos, `None` no suma y los empates se devuelven completos. Los puntajes anteriores (RAG 1 · FT 0 · PEFT 1 con la evidencia; 0 · 1 · 2 con la hipótesis) **quedan sustituidos** por los de este registro.

## 1. Punto de partida

La consigna propone una hipótesis inicial: `informacion_cambia_seguido=False`, `problema_de_formato_o_tono=True`, `dataset_grande_y_de_calidad=False`, `presupuesto_limitado_o_iterar_rapido=True` y `necesita_multiples_variantes=False`. Con los pesos oficiales da **RAG 2 · FT 1 · PEFT 3** y elegiría PEFT. Se trató como hipótesis, no como dato.

## 2. Verificación criterio por criterio

1. **Cambio de información.** `git log --date=short -- src/cliente.py src/rag/reintentos.py src/rag/errores.py` devuelve 2026-10-23, 2026-10-27, 2026-11-12 y 2026-11-16. Las cuatro fechas caen en los 30 días previos a HEAD (2026-11-16). El primer commit del repositorio es del 2026-10-08 (39 días de historial). Resultado: **Sí, parcial**. Contradice la hipótesis: para esta tarea, el «conocimiento» es el catálogo de errores y acciones, y ese catálogo crece con el código.
2. **Formato o tono.** No existe `data/personalizacion/respuestas_modelo_base.json` ni ninguna otra muestra de respuestas del modelo base. Resultado: **no verificado (`None`)**. No se trató como `False` y no se ejecutó Gemini para generar la muestra (sin llamadas de pago).
3. **Dataset.** 35 ejemplos frente a 200. Resultado: **No**.
4. **Presupuesto o iteración.** Hay tres indicios en el repositorio: el texto de `--pausa` en `src/indexar_corpus.py`, la cuota gratuita de embeddings en `README-bloque24.md` y los errores 429 *free tier* en `README-bloque28.md`. Resultado: **Sí, parcial** (no hay una cifra de presupuesto).
5. **Variantes.** Un único esquema y ningún requisito de variantes. Resultado: **No, parcial**.

## 3. Puntuación

`.venv\Scripts\python.exe -m src.decision_personalizacion`:

```text
== Puntuación con valores comprobados [PROVISIONAL: hay criterios sin verificar]: {'RAG': 5, 'Fine-tuning completo': 0, 'PEFT': 1}
   Primer lugar: RAG
   No verificados: ['problema_de_formato_o_tono']; máximo posible: {'RAG': 5, 'Fine-tuning completo': 1, 'PEFT': 3}
   Si {'problema_de_formato_o_tono': True}: {'RAG': 5, 'Fine-tuning completo': 1, 'PEFT': 3} -> primer lugar ['RAG']
   Si {'problema_de_formato_o_tono': False}: {'RAG': 5, 'Fine-tuning completo': 0, 'PEFT': 1} -> primer lugar ['RAG']

== Puntuación con valores de la hipótesis inicial: {'RAG': 2, 'Fine-tuning completo': 1, 'PEFT': 3}
   Primer lugar: PEFT

== Puntuación con valores del ejemplo oficial del curso: {'RAG': 0, 'Fine-tuning completo': 3, 'PEFT': 3}
   Empatadas en primer lugar: ['Fine-tuning completo', 'PEFT']
```

- **Empates:** solo el ejemplo oficial empata (FT y PEFT con 3). Se informa como empate, sin ganadora; el código no elige el primero del diccionario.
- **Provisional:** el puntaje con la evidencia lleva la marca `PROVISIONAL` porque el formato no está medido. Su primer lugar no depende de ese criterio, pero sí de dos criterios de comprobación parcial. Si información y presupuesto resultaran «No» y el formato «Sí», quedaría RAG 0 · FT 1 · PEFT 2 y ganaría PEFT.
- **Sensibilidad** (un criterio cada vez, sobre los valores comprobados): RAG se mantiene primero en los seis cambios posibles (2·0·1, 5·1·3, 5·0·1, 5·2·2, 3·0·0 y 5·0·3).

## 4. Decisión: por qué Prompt + Pydantic y no PEFT ahora

RAG lidera porque el catálogo cambia y porque conviene iterar barato. Las dos razones apuntan a **no meter el catálogo en los pesos del modelo**. Prompt + Pydantic las cumple dejando el catálogo como contexto editable del prompt, sin un índice vectorial que no hace falta para 5 categorías. A la vez, ataca el problema real, que es el formato, y eso RAG no lo resuelve. Contra PEFT, hoy:

- No está demostrado que exista el problema de formato que PEFT resolvería.
- Hay 35 ejemplos, y el criterio del curso pide 200 o más con revisión.
- Con el SDK instalado, PEFT exige el modo Vertex y un dataset en Cloud Storage; el proyecto funciona con una clave de la API de Gemini. **No se verificó que PEFT esté disponible** para la cuenta ni para ningún modelo.
- No se sabe cuánto costaría.
- Un adapter congelaría un catálogo que cambia con frecuencia.

PEFT queda como evolución futura, con un disparador medible: que la línea base incumpla el formato en ≥ 15 % de 20 respuestas reales. **No se entrenó ningún modelo.**

## 5. Pruebas

```text
tests/test_personalizacion_decision.py  38 passed
```

Las pruebas cubren:

- Los pesos oficiales y los escenarios A y B.
- La sensibilidad: cada criterio aislado suma exactamente su fila; invertir cada criterio de la hipótesis suma o resta su fila; el primer lugar tras cada inversión; `None` probado con ambos valores.
- `None` frente a `False` y el resultado provisional.
- Los valores comprobados del repositorio.
- Los empates de tres vías y en cero.
- El documento generado.

Antes de la corrección, la primera ejecución dio 1 fallo en un test propio: el historial simulado (20/10 → 16/11) tenía 27 días, por debajo del mínimo de 30 de la regla. Se corrigió la fecha del test, no la regla.

## 6. Conclusión

Con los pesos oficiales, la hipótesis inicial elegiría PEFT, pero la evidencia del repositorio da un primer lugar **provisional** para RAG (5 · 0 · 1). La recomendación aplica el principio que premia RAG (conocimiento externo y actualizable) con la herramienta más barata que, además, ataca el formato: Prompt + Pydantic. No se afirma que ninguna técnica supere a otra sin experimentos.
