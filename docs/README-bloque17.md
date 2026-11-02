# Bloque 17 — Instrucciones de integración

Este paquete es una **plantilla de trabajo**, NO evidencia de que la tarea ya esté completada.

1. Copia `src/preparar_revision_bloque17.py` y `docs/limites_metrica.md` a las mismas rutas de tu proyecto.
2. Ejecuta primero el Bloque 16 y obtén al menos 20 registros con `consulta`, `referencia`, `respuesta` y `f1`.
3. Guarda esos registros en `docs/resultados_metricas.json` o ajusta `--entrada`.
4. Desde la raíz ejecuta: `python -m src.preparar_revision_bloque17 --entrada docs/resultados_metricas.json`
5. El script guarda `docs/revision_manual_bloque17.json` con hasta 10 casos (5 mínimos + 5 máximos). No inventa juicios: completa manualmente los campos `correccion_factual` (sí/no/parcialmente), `completitud` (sí/no/parcialmente), `contradiccion` (sí/no) y `nota`.
6. Tras leer cada caso, rellena `docs/limites_metrica.md` con ejemplos de los hallazgos reales y tu recomendación de uso.
7. Valida los datos: 20+ respuestas, 10+ revisiones sin duplicados, notas justificadas, 4 secciones completas.
8. Versiona solo después de comprobar la evidencia: `git add src/preparar_revision_bloque17.py docs/revision_manual_bloque17.json docs/limites_metrica.md && git commit -m "Documenta revisión cualitativa y límites de la métrica" && git push origin main`.

Si el JSON de tu Bloque 16 usa nombres de campos distintos, adapta el mapeo en el script antes de ejecutarlo.
