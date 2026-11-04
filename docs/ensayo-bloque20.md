# Evidencia — Bloque 20: Manejo de errores y verificación completa

**Estado:** Validación técnica satisfactoria. Publicación en GitHub pendiente de confirmar.

## 1. Objetivo

Verificar el funcionamiento de la cadena desarrollada en los Bloques 18 y 19, extendida con mecanismos de recuperación ante errores mediante `with_fallbacks`, captura general de excepciones con `try/except` y registro de errores.

## 2. Entorno de ejecución

- Sistema operativo: Windows.
- Python: 3.13.5.
- pytest: 9.2.0.
- Modelo utilizado: `gemini-3.5-flash-lite`.
- Framework de orquestación: LangChain.
- Entorno virtual: `.venv`.

## 3. Comandos de validación

```powershell
python -m pytest tests/test_enrutamiento.py tests/test_orquestacion.py -v
python -m pytest tests/ -v
python -m src.enrutamiento
```

## 4. Resultados observados

### 4.1. Pruebas de los Bloques 19 y 20

**Resultado: 15 pruebas aprobadas en 1,16 segundos.**

Se verificaron:

- Las tres rutas de enrutamiento: pregunta, queja y sugerencia.
- La ruta predeterminada ante una categoría desconocida.
- La normalización de categorías.
- La ejecución del fallback ante un fallo simulado.
- La ausencia de activación del fallback cuando la ruta principal funciona.
- La recuperación ante un fallo de clasificación.
- La captura general de excepciones.
- La conservación del funcionamiento normal de las rutas.

### 4.2. Pruebas de regresión completas

**Resultado: 61 pruebas aprobadas en 1,01 segundos.**

La suite completa no presentó pruebas fallidas.

Las pruebas cubrieron funcionalidades implementadas en los bloques anteriores, incluyendo el cliente de Gemini, reintentos, procesamiento de texto, métricas y orquestación.

## 5. Integración real con Gemini

Se ejecutó:

```powershell
python -m src.enrutamiento
```

Se procesaron tres mensajes reales de prueba.

### Caso 1 — Pregunta técnica

**Entrada:** ¿Cómo soluciono un ModuleNotFoundError al ejecutar Python?

**Resultado:** Gemini explicó el error, identificó causas posibles, propuso comprobaciones del entorno y solicitó información adicional.

### Caso 2 — Queja

**Entrada:** La aplicación se cierra cada vez que intento iniciar sesión.

**Resultado:** Gemini generó una respuesta empática, reconoció el inconveniente y solicitó antecedentes técnicos para investigar el problema.

### Caso 3 — Sugerencia

**Entrada:** Sería útil tener un modo oscuro en la aplicación.

**Resultado:** Gemini agradeció la sugerencia y explicó que podría evaluarse, sin garantizar su implementación.

Las solicitudes HTTP observadas finalizaron con código `200 OK`.

No se observaron fallos durante esta ejecución real.

## 6. Verificación de resiliencia

Las pruebas automatizadas comprobaron que:

1. Cuando una ruta protegida falla, `with_fallbacks` ejecuta una respuesta alternativa.
2. Cuando la ruta principal funciona, no se ejecuta el fallback.
3. Cuando falla la clasificación, el manejador general devuelve una respuesta segura.
4. Cuando falla una ruta no protegida individualmente, la captura general evita que la excepción llegue al usuario.
5. Los mecanismos de recuperación no alteran el comportamiento normal de las rutas.

Los fallos fueron simulados mediante pruebas automatizadas. No se provocaron fallos reales en la API de Gemini.

## 7. Checklist de orquestación

- [x] La normalización de categorías está verificada mediante pruebas.
- [x] Las tres rutas tienen pruebas individuales.
- [x] La ruta predeterminada está probada.
- [x] Las rutas utilizan prompts diferenciados.
- [x] Existe al menos una ruta protegida mediante `with_fallbacks`.
- [x] Se comprobó la activación del fallback ante un error simulado.
- [x] El manejo general de excepciones devuelve una respuesta segura.
- [x] Se verificaron los fallos simulados de clasificación y de rutas.
- [x] La suite de regresión completa fue exitosa.
- [x] La integración real con Gemini generó respuestas.
- [x] Los resultados registrados corresponden a ejecuciones observadas.

**Observación:** la suite verifica la normalización y la ruta predeterminada. No constituye una garantía de que Gemini siempre clasifique correctamente cualquier mensaje ambiguo.

## 8. Conclusión

La implementación cumple los objetivos técnicos verificados del Bloque 20.

La cadena conserva el enrutamiento condicional, incorpora recuperación ante errores mediante fallbacks y captura general de excepciones, y mantiene las funcionalidades cubiertas por las pruebas de los bloques anteriores.

**Resultados finales:**

- 15/15 pruebas de enrutamiento y orquestación aprobadas.
- 61/61 pruebas de la suite completa aprobadas.
- 3/3 mensajes reales procesados satisfactoriamente con Gemini.

**Estado final:** Bloque 20 validado técnicamente. Pendiente de confirmar commit y push en GitHub.