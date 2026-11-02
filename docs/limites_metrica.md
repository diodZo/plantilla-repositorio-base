# Límites de la métrica de evaluación — Bloque 17

**Fecha de los resultados:** 2026-11-02 (UTC, según registros)  
**Muestra:** 20 respuestas reales del cliente Gemini sobre conceptos de Python; 10 revisadas cualitativamente.  
**Fuente:** `docs/resultados_metricas.json` y `docs/revision_manual_bloque17.json`.

## Qué mide

La implementación calcula **precisión, cobertura y F1 léxicos** sobre tokens normalizados; usa `Counter` para contar coincidencias con repeticiones. No verifica por sí misma la verdad factual, equivalencia semántica ni implicaciones de una oración.

Resultados globales de las 20 respuestas: precisión media **0.2813**, cobertura media **0.7072**, F1 medio **0.3979**. Estos son promedios de superposición léxica, **no porcentajes de acierto factual**.

## Modos de falla conocidos

1. **Sinónimos y paráfrasis penalizados.** La respuesta sobre listas usa «mutable» donde la referencia usa «modificable» (F1 **0.579**), aun cuando expresan la misma propiedad.
2. **Respuestas correctas pero con explicación más amplia reciben baja precisión.** En la consulta sobre funciones, el F1 fue **0.146**; el modelo explicó agrupación y reutilización de código, pero también omitió argumentos y devolución de resultados. Es un caso de coincidencia léxica baja **y** completitud parcial; no se puede interpretar solo como fracaso total.
3. **Formulación técnica menos precisa puede pasar desapercibida.** Para `print`, la respuesta habla de mostrar contenido «en la pantalla», mientras la referencia usa «salida estándar», que también puede redirigirse (F1 **0.276**).
4. **Generalizaciones incompletas.** El caso de `for` menciona objetos secuencia en vez de todos los iterables (F1 **0.273**). El detalle técnico se descubre leyendo el texto, no mirando el número.
5. **Limitación metodológica no observada en esta muestra seleccionada:** una cifra, fecha, nombre o negación incorrecta puede conservar F1 alto, ya que cada token pesa igual. Esta advertencia proviene del análisis conceptual del Bloque 16; **no se encontró una contradicción explícita** en los diez casos seleccionados.

## Muestra revisada

Se evaluaron **10 casos diferentes** entre los **20 resultados reales**: los cinco con F1 menor y los cinco con F1 mayor. En cada caso se comparó referencia y respuesta mediante **corrección factual**, **completitud** y **contradicción**, con justificación individual en `docs/revision_manual_bloque17.json`.

Distribución de la rúbrica: factual **8 sí**, **2 parcialmente**, **0 no**; completitud **7 sí**, **3 parcialmente**, **0 no**; **0 contradicciones explícitas**.

La evaluación cualitativa es una **propuesta de revisión asistida**, para validación final del estudiante; no sustituye su juicio personal ni una verificación externa exhaustiva.

## Recomendación de uso

Usar precisión, cobertura y F1 para **comparar sistemáticamente la superposición de palabras** y priorizar revisiones; **no usarlos como único indicador de corrección**. Revisar manualmente respuestas con datos sensibles (números, fechas, negaciones, nombres) y las que contienen sinónimos, generalizaciones o detalles técnicos. Registrar la referencia, el motivo del juicio y la fecha al actualizar este documento.
