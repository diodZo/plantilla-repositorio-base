# Bloque 30 — Elegir la estrategia de personalización

## Objetivo

Decidir con evidencia cómo conseguir un comportamiento consistente (clasificar errores del proyecto en un JSON fijo, ver el Bloque 29). Se comparan RAG, fine-tuning completo y PEFT con el método de puntuación del curso, y se añade **Prompt + Pydantic** como línea base práctica. El resultado está en `docs/decision_personalizacion.md`, generado por código.

## Arquitectura

| Archivo | Responsabilidad |
|---|---|
| `src/personalizacion/decision.py` | Criterios, `PESOS`, `puntuar` (puntos, empates, criterios no verificados y máximo posible), recogida de evidencia del repositorio y `recomendar` |
| `src/personalizacion/documento_decision.py` | `generar_documento`: Markdown con exactamente cuatro secciones `##` |
| `src/personalizacion/salida_estructurada.py` | Línea base: `SalidaClasificacion` (Pydantic estricto), prompt few-shot y `GenerateContentConfig` con `response_schema` (todo local) |
| `src/decision_personalizacion.py` | CLI: `python -m src.decision_personalizacion` |

## Método de decisión

Pesos oficiales del PDF del Bloque 30 (tabla `PESOS` de `src/personalizacion/decision.py`):

| Criterio | RAG | Fine-tuning completo | PEFT |
|---|---:|---:|---:|
| `informacion_cambia_seguido` | 3 | 0 | 0 |
| `problema_de_formato_o_tono` | 0 | 1 | 2 |
| `dataset_grande_y_de_calidad` | 0 | 2 | 1 |
| `presupuesto_limitado_o_iterar_rapido` | 2 | 0 | 1 |
| `necesita_multiples_variantes` | 0 | 0 | 2 |

> **Corrección:** la primera versión usaba pesos reconstruidos (1 punto por criterio) porque el PDF no estaba en el repositorio. Se reemplazaron por los oficiales y se sustituyeron todos los puntajes anteriores.

- Cada criterio vale `True`, `False` o `None` (no verificado). `None` no suma y **no equivale a `False`**: se informa aparte, junto con el **máximo posible** de cada estrategia, y marca el resultado como **provisional** (`ResultadoDecision.provisional`). Un puntaje provisional no es una decisión final plenamente fundamentada.
- `puntuar` devuelve los puntos y la lista `empatadas` en el orden fijo de `ESTRATEGIAS`. `ganadora` solo existe si hay un único primer lugar. **Nunca** se toma la primera clave de un diccionario (hay un test que invierte el orden de entrada).
- Exige exactamente los cinco criterios y rechaza los valores que no sean booleanos.
- Análisis sin reglas nuevas de puntuación: `escenarios_no_verificados` puntúa cada combinación posible de los criterios `None`, y `sensibilidad` cambia cada criterio por separado.

## Verificación de la hipótesis inicial

| Criterio | Hipótesis | Comprobado | Evidencia |
|---|---|---|---|
| `informacion_cambia_seguido` | No | **Sí** (parcial) | `git log` sobre `src/cliente.py`, `src/rag/reintentos.py` y `src/rag/errores.py`: 4 commits en los 30 días previos a HEAD (23/10, 27/10, 12/11, 16/11). El catálogo de errores, que es el «conocimiento» de esta tarea, cambia con el código. El historial es de 39 días: no prueba una frecuencia sostenida |
| `problema_de_formato_o_tono` | Sí | **No verificado** | No existe una muestra de 20 respuestas del modelo base. No se inventa ningún porcentaje |
| `dataset_grande_y_de_calidad` | No | No | 35 ejemplos < 200 |
| `presupuesto_limitado_o_iterar_rapido` | Sí | Sí (parcial) | Indicios de cuota limitada: `--pausa` «para respetar la cuota por minuto», cuota gratuita de embeddings (README 24) y errores 429 *free tier* (README 28). No hay un presupuesto monetario documentado |
| `necesita_multiples_variantes` | No | No (parcial) | Un único esquema de salida y ningún requisito de variantes en el repositorio |

## Resultado real

| Escenario | RAG | FT completo | PEFT | Primer lugar |
|---|---:|---:|---:|---|
| A. Hipótesis inicial | 2 | 1 | 3 | PEFT |
| B. Ejemplo oficial del curso (formato y dataset Sí) | 0 | 3 | 3 | **Empate:** Fine-tuning completo y PEFT |
| **Criterios comprobados del repositorio (PROVISIONAL)** | **5** | **0** | **1** | RAG |
| ↳ si el formato (no verificado) resultara Sí | 5 | 1 | 3 | RAG |
| ↳ si el formato resultara No | 5 | 0 | 1 | RAG |

Sensibilidad con los valores comprobados (un criterio cada vez):

| Criterio cambiado | Puntos (RAG · FT · PEFT) | Primer lugar |
|---|---|---|
| información Sí → No (parcial) | 2 · 0 · 1 | RAG |
| dataset No → Sí | 5 · 2 · 2 | RAG |
| presupuesto Sí → No (parcial) | 3 · 0 · 0 | RAG |
| variantes No → Sí (parcial) | 5 · 0 · 3 | RAG |

Lectura:

- Con la evidencia, RAG lidera de forma **provisional**, y el criterio no verificado (formato) no cambia el primer lugar.
- La ventaja de RAG se apoya en dos criterios de comprobación **parcial**: el cambio del catálogo de errores (+3) y el presupuesto (+2). Si ambos resultaran «No» y el formato «Sí», el primer lugar pasaría a PEFT (RAG 0 · FT 1 · PEFT 2). Por eso no se presenta como una decisión final.
- La hipótesis inicial (PEFT) queda contradicha por el criterio de información cambiante. El ejemplo oficial confirma que el método devuelve el empate FT/PEFT sin elegir un ganador.

## Comparación técnica y económica para este caso

**RAG.** Es fuerte cuando hay conocimiento documental que se actualiza: el catálogo de errores y acciones podría recuperarse o inyectarse en el prompt y cambiar sin reentrenar, algo valioso porque cambió 4 veces en un mes. Pero RAG no enseña un formato de salida: recuperar más contexto no garantiza JSON con dos claves exactas. Además, la tarea no requiere buscar entre muchos documentos; el catálogo cabe en un prompt.

**Fine-tuning completo.** Podría fijar el formato y el criterio de clasificación en los pesos. Sus costos son los más altos: requiere muchos más datos (el criterio del curso pide 200 o más con revisión), cómputo, un nuevo entrenamiento cada vez que cambie el catálogo y un modelo propio que mantener y versionar. No hay ningún experimento que muestre que sea mejor en este caso, y en el SDK tampoco se verificó que exista para los modelos disponibles.

**PEFT (adapters).** Entrena pocos parámetros adicionales, así que suele ser más barato y rápido de iterar que un ajuste completo cuando la infraestructura lo admite, y permite varios adapters sobre un mismo modelo base. Pero un adapter pequeño (`ADAPTER_SIZE_ONE`) no garantiza un comportamiento correcto: sigue necesitando datos suficientes y una evaluación. Con google-genai 2.34.0, PEFT solo es enviable en modo Vertex y con el dataset en Cloud Storage; el proyecto hoy usa una clave de la API de Gemini.

**Prompt + Pydantic (línea base).** Instrucción de sistema, pocos ejemplos tomados del dataset, salida estructurada (`response_mime_type="application/json"` + `response_schema=SalidaClasificacion`) y validación estricta en el cliente (`extra="forbid"`, categorías `Literal`). Ataca directamente el síntoma (formato y categorías cerradas), no requiere entrenamiento, el catálogo se actualiza editando el prompt y el costo se limita a las llamadas de inferencia. Lo que no resuelve por sí sola es la **calidad** de la clasificación: si el modelo elige mal la categoría dentro del esquema, Pydantic lo acepta. Esa tasa hay que medirla con el conjunto de validación (`categoria_coincide`).

## Por qué no soft-prompting

Soft-prompting (prompt tuning) entrena vectores continuos que se anteponen a la entrada en el espacio de embeddings del modelo. Requiere acceso a esos embeddings y al cálculo de gradientes a través del modelo congelado. La API gestionada de Gemini que se usa en el curso solo acepta texto y, para tuning, expone `TuningMode` con `FULL` y `PEFT_ADAPTER`; no ofrece ningún modo de prompt tuning ni acceso a los embeddings de entrada. Por eso queda solo como concepto teórico.

## Decisión

RAG lidera el puntaje provisional por dos razones: el catálogo de errores cambia (+3) y conviene iterar barato (+2). Ambas se cumplen manteniendo el catálogo **fuera de los pesos del modelo**, como contexto del prompt que se edita sin reentrenar, que es el principio que premia RAG. Un índice vectorial no se justifica para un catálogo de 5 categorías y unas 13 clases de error, que cabe en el prompt. Y RAG no resuelve el formato, que es el problema planteado. Si el catálogo creciera hasta no caber en el prompt, se podría recuperar con la infraestructura RAG de los Bloques 24–28.

**Implementación inmediata: Prompt + Pydantic, con el catálogo de errores como contexto actualizable. Evolución futura: PEFT**, solo si esa línea base incumple el formato en ≥ 15 % de una muestra de 20 respuestas reales y, además, se reúnen los datos (≈ 165 ejemplos más con revisión), la infraestructura (Vertex + bucket), la confirmación de un modelo que admita tuning y el presupuesto. El detalle está en `docs/decision_personalizacion.md`.

## Cómo regenerar

```powershell
python -m src.decision_personalizacion
# Con una muestra real del modelo base (≥ 20 respuestas), el criterio de formato pasa a medirse:
python -m src.decision_personalizacion --respuestas-base data\personalizacion\respuestas_modelo_base.json
```

Formato de la muestra: `{"origen": "gemini_base", "respuestas": ["{...}", ...]}`.

## Pruebas

`python -m pytest tests/test_personalizacion_decision.py -v`: 38 pruebas offline. Cubren los pesos oficiales, el escenario A (2/1/3), el escenario B (0/3/3 con empate FT/PEFT), la sensibilidad (cada criterio aislado suma exactamente su fila; invertir cada criterio de la hipótesis suma o resta su fila y cambia o no el primer lugar; `None` se prueba con ambos valores), `None` distinto de `False` y el resultado provisional, los valores comprobados del repositorio (5/0/1 y sus escenarios), los empates (incluido el empate total y el orden invertido), los no verificados con máximo posible, la validación de entrada, la evidencia con fechas y archivos simulados, la muestra de formato con 15 % exacto, cuatro secciones exactas, la ausencia de afirmaciones de entrenamiento o superioridad, el CLI en `tmp_path`, el esquema Pydantic, la configuración local de salida estructurada y la importación sin red ni clientes.

## Limitaciones

- El resultado con la evidencia es provisional: el criterio de formato no está medido.
- Tres criterios quedan como «verificado parcial»: se basan en indicios del repositorio, no en una declaración del equipo. Dos de ellos (información y presupuesto) sostienen el primer lugar de RAG.
- La evidencia de cambios se mide sobre el HEAD y se moverá con nuevos commits; hay que regenerar el documento.
- La línea base Prompt + Pydantic está construida, pero no medida.
