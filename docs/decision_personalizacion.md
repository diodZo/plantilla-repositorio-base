# Decisión de personalización — Bloque 30

Generado con `python -m src.decision_personalizacion` (repositorio en HEAD del 2026-11-16). No se llamó a la API de Gemini ni se creó ningún trabajo de tuning.

## 1. El problema

Queremos que el modelo convierta un mensaje de error técnico del proyecto en un JSON con exactamente dos claves, `categoria` y `accion_sugerida`, con categorías fijas (`red`, `autenticacion`, `cuota`, `entorno`, `consistencia_indice`) y acciones coherentes con la política del código (`src/cliente.py`, `src/rag/reintentos.py`, `src/rag/errores.py`): los fallos de red y 5xx se reintentan con backoff exponencial, los 429 también pero requieren bajar el ritmo, y las credenciales nunca se reintentan.

Es un problema de **consistencia de clasificación y formato**, no de conocimiento documental.

**Evidencia disponible:**

- Dataset propio validado: 25 ejemplos de entrenamiento y 10 de validación (35 en total), sin errores de validación y con el mismo número de ejemplos en cada categoría.
- Muestra de respuestas reales del modelo base: No existe una muestra de respuestas reales del modelo base (respuestas_modelo_base.json). No se calcula ni se supone un porcentaje de incumplimiento.
- Por lo tanto, todavía **no está demostrado** que el modelo base falle en el formato: es la hipótesis que motiva el análisis.

## 2. Resultado del método de decisión

Cada criterio verdadero suma a cada estrategia el peso oficial del curso (tabla `PESOS` de `src/personalizacion/decision.py`). Un criterio no verificado no suma y **no se trata como «No»**.

| Criterio | RAG | Fine-tuning completo | PEFT |
|---|---:|---:|---:|
| `informacion_cambia_seguido` | 3 | 0 | 0 |
| `problema_de_formato_o_tono` | 0 | 1 | 2 |
| `dataset_grande_y_de_calidad` | 0 | 2 | 1 |
| `presupuesto_limitado_o_iterar_rapido` | 2 | 0 | 1 |
| `necesita_multiples_variantes` | 0 | 0 | 2 |

| Criterio | Umbral del curso | Hipótesis inicial | Valor comprobado | Estado | Cómo se comprobó |
|---|---|---|---|---|---|
| `informacion_cambia_seguido` | La información cambia al menos mensualmente. | No | Sí | verificado_parcial | El catálogo de errores y acciones (`src/cliente.py`, `src/rag/reintentos.py`, `src/rag/errores.py`) cambió en 4 commits durante los 30 días previos a HEAD (2026-11-16): 2026-10-23, 2026-10-27, 2026-11-12, 2026-11-16. Historial total del repositorio: 39 días. Ventana corta y proyecto en desarrollo activo: no demuestra una frecuencia sostenida. |
| `problema_de_formato_o_tono` | ≥ 15 % de incumplimiento de formato o tono en una muestra de 20 respuestas. | Sí | No verificado | no_verificado | No existe una muestra de respuestas reales del modelo base (respuestas_modelo_base.json). No se calcula ni se supone un porcentaje de incumplimiento. |
| `dataset_grande_y_de_calidad` | ≥ 200 ejemplos etiquetados y revisión satisfactoria de 20. | No | No | verificado | Hay 35 ejemplos etiquetados; el criterio del curso pide al menos 200. |
| `presupuesto_limitado_o_iterar_rapido` | Restricciones de presupuesto o necesidad real de iterar rápido. | Sí | Sí | verificado_parcial | Indicios indirectos de operar con cuota limitada: `src/indexar_corpus.py` («respetar la cuota por minuto»); `docs/README-bloque24.md` («cuota gratuita de embeddings limita»); `docs/README-bloque28.md` («errores 429 de cuota *free tier*»). No hay un presupuesto monetario documentado. |
| `necesita_multiples_variantes` | Se necesita más de una variante personalizada. | No | No | verificado_parcial | La tarea define un único esquema de salida ['categoria', 'accion_sugerida'] y no hay en el repositorio ningún requisito de una segunda variante (otro idioma, tono o cliente). |

**Puntaje PROVISIONAL con los criterios comprobados** (hay criterios sin verificar; no es una decisión final plenamente fundamentada):

| Estrategia | Puntos | Máximo si los no verificados fueran «Sí» |
|---|---|---|
| RAG | 5 | 5 |
| Fine-tuning completo | 0 | 1 |
| PEFT | 1 | 3 |

**Primer lugar sin empate:** RAG (5 puntos).

Qué pasaría con cada valor posible de los criterios no verificados:

| Supuesto | Puntos | Primer lugar |
|---|---|---|
| `problema_de_formato_o_tono` = Sí | RAG 5 · Fine-tuning completo 1 · PEFT 3 | RAG |
| `problema_de_formato_o_tono` = No | RAG 5 · Fine-tuning completo 0 · PEFT 1 | RAG |

El primer lugar **no depende** de los criterios no verificados.

Sensibilidad (cambiando un solo criterio cada vez respecto de los valores comprobados):

| Criterio cambiado | De → a | Puntos | Primer lugar |
|---|---|---|---|
| `informacion_cambia_seguido` (comprobación parcial) | Sí → No | RAG 2 · Fine-tuning completo 0 · PEFT 1 | RAG |
| `problema_de_formato_o_tono` | No verificado → Sí | RAG 5 · Fine-tuning completo 1 · PEFT 3 | RAG |
| `problema_de_formato_o_tono` | No verificado → No | RAG 5 · Fine-tuning completo 0 · PEFT 1 | RAG |
| `dataset_grande_y_de_calidad` | No → Sí | RAG 5 · Fine-tuning completo 2 · PEFT 2 | RAG |
| `presupuesto_limitado_o_iterar_rapido` (comprobación parcial) | Sí → No | RAG 3 · Fine-tuning completo 0 · PEFT 0 | RAG |
| `necesita_multiples_variantes` (comprobación parcial) | No → Sí | RAG 5 · Fine-tuning completo 0 · PEFT 3 | RAG |

**Ejemplo oficial del curso** (formato Sí, dataset Sí, resto No; solo como referencia del método): RAG 0, Fine-tuning completo 3, PEFT 3. **Empate en el primer lugar:** Fine-tuning completo, PEFT (3 puntos).

**Con la hipótesis inicial (solo como contraste, no como evaluación final):**

| Estrategia | Puntos |
|---|---|
| RAG | 2 |
| Fine-tuning completo | 1 |
| PEFT | 3 |

**Primer lugar sin empate:** PEFT (3 puntos).

La evidencia contradice o no confirma la hipótesis en: `informacion_cambia_seguido` (No → Sí), `problema_de_formato_o_tono` (Sí → No verificado).

## 3. Técnica elegida y por qué

**Implementación inmediata: Prompt + Pydantic, con el catálogo de errores como contexto externo y actualizable (el principio que puntúa RAG, sin índice vectorial).** **Evolución futura: PEFT, solo si la línea base incumple el formato en ≥ 15 % de una muestra de 20 y se reúnen los datos y la infraestructura necesarios.**

Motivo principal: RAG lidera de forma provisional por los criterios de información cambiante y presupuesto; ambos se satisfacen manteniendo el catálogo fuera de los pesos del modelo, y el catálogo es pequeño, así que no hace falta recuperación sobre un corpus. RAG no resuelve el formato, que es el problema planteado: eso lo cubre la validación Pydantic; el criterio de formato sigue sin medirse.

- **Datos:** con 35 ejemplos no se cumple el criterio de dataset grande (200); sí alcanzan para ejemplos few-shot en el prompt y para un conjunto de control.
- **Formato:** el contrato (`SalidaClasificacion` en `src/personalizacion/salida_estructurada.py`: categorías `Literal`, `extra="forbid"`, acción no vacía) puede imponerse con salida estructurada (`response_mime_type="application/json"` + `response_schema`) y validarse siempre en el cliente. Eso ataca directamente el síntoma sin entrenar.
- **Infraestructura:** con google-genai 2.34.0, el SDK solo acepta PEFT (`tuning_mode`, `adapter_size`) en modo Vertex y con el dataset en Cloud Storage; rechaza la combinación con ejemplos inline en ambos modos. El proyecto usa una clave de la API de Gemini (modo Developer API), donde esos parámetros se rechazan.
- **Presupuesto:** no hay presupuesto de tuning documentado ni tarifas de entrenamiento en `data/tarifas_gemini.json`; Prompt + Pydantic solo consume las llamadas de inferencia que ya existen.
- **Esfuerzo humano:** la línea base reutiliza los 35 ejemplos actuales; el tuning exigiría etiquetar y revisar al menos 165 más (ver sección 4).
- **Conocimiento cambiante:** el catálogo de errores cambia con el código. Mantenerlo en el prompt (o recuperarlo) permite actualizarlo sin reentrenar; un adapter lo congelaría en el momento del entrenamiento.

No se afirma que PEFT, fine-tuning o RAG sean mejores o peores que el prompt: no hay experimentos que lo midan.

## 4. Qué necesitaríamos para ejecutarla

| Elemento | Situación actual | Pendiente |
|---|---|---|
| Ejemplos etiquetados | 35 (25 entrenamiento + 10 validación) | 165 más para llegar a 200 (mínimo orientativo del curso, no de la API) |
| Cobertura por categoría | red: 7, autenticacion: 7, cuota: 7, entorno: 7, consistencia_indice: 7 | ≈ 40 por categoría para mantener el balance (5 categorías) |
| Revisión manual | No realizada | Revisar 20 ejemplos con un criterio escrito |
| Tiempo de etiquetado | — | ≈ 390 min (≈ 6,5 h). **Supuesto:** 2 min por ejemplo nuevo y 3 min por ejemplo revisado; no medido |
| Muestra de formato del modelo base | No existe | 20 respuestas reales guardadas en `data/personalizacion/respuestas_modelo_base.json`; umbral 15% |
| Línea base Prompt + Pydantic | Esquema y configuración construidos localmente | Medir su incumplimiento con la misma muestra antes de decidir tuning |
| SDK: ejemplos inline + PEFT | gemini_developer_api: rechazada; vertex: rechazada (conversores locales del SDK) | — |
| SDK: dataset en Cloud Storage + PEFT | gemini_developer_api: rechazada; vertex: aceptada (conversores locales del SDK) | — |
| Requisitos técnicos | Clave de la API de Gemini (modo Developer API) | Para PEFT: proyecto de Google Cloud con Vertex, bucket de Cloud Storage, dataset en el formato JSONL que exija el servicio y cliente en modo Vertex |
| Disponibilidad de tuning en modelo y cuenta | **No verificada** (no se consultó la API); `MODELOS_TUNING_VERIFICADOS` está vacío | Confirmar en la documentación oficial y en la cuenta qué modelo base admite tuning supervisado con adapters |
| Presupuesto | **Pendiente de verificar**; no se presupone ningún costo | Obtener las tarifas oficiales de entrenamiento y del modelo ajustado, y aprobar un tope |
| Autorización | `crear_trabajo_tuning` bloqueado por defecto | Autorización explícita, variable de entorno y modelo verificado (las tres condiciones) |
