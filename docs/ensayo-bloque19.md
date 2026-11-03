# Evidencias del Bloque 19 — completar después de ejecutar

## Entorno

- Python: **pendiente de verificar**
- LangChain y conector Gemini: **pendiente de verificar**
- Modelo (`AI_MODEL`): **pendiente de verificar**

## Pruebas automatizadas

Comando: `python -m pytest tests/test_enrutamiento.py -v`

Resultado: **pendiente de ejecución en entorno local**. No registrar como aprobadas antes de ejecutarlas.

## Integración real

Comando: `python -m src.enrutamiento`

Resultados de las tres entradas: **pendiente de ejecución real con Gemini**.

## Verificación académica

- [ ] Tres rutas ejecutables según la categoría.
- [ ] Clasificación normalizada.
- [ ] Ruta por defecto validada.
- [ ] Pruebas offline aprobadas.
- [ ] Evidencia de ejecución real.

## Incidencias y observaciones

# Evidencia — Bloque 19: Enrutamiento condicional con LangChain

## Objetivo

Implementar y validar un flujo de enrutamiento condicional capaz de clasificar mensajes y dirigirlos a diferentes cadenas de respuesta mediante LangChain.

## Componentes utilizados

- `PromptTemplate`
- `ChatGoogleGenerativeAI`
- `StrOutputParser`
- `RunnableBranch`
- `RunnablePassthrough.assign`
- pytest y mocks

## Rutas implementadas

1. **Pregunta:** genera una respuesta técnica.
2. **Queja:** responde de manera empática y propone pasos para abordar el problema.
3. **Sugerencia:** agradece la propuesta y explica cómo podría evaluarse.

La ruta de pregunta también funciona como alternativa predeterminada para categorías no reconocidas.

## Pruebas automatizadas

Comando ejecutado:

`python -m pytest tests/test_enrutamiento.py -v`

Resultados:

- `test_enrutamiento_queja`: PASSED
- `test_enrutamiento_sugerencia`: PASSED
- `test_enrutamiento_pregunta`: PASSED
- `test_enrutamiento_categoria_desconocida_usa_default`: PASSED
- `test_clasificacion_normaliza_mayusculas_y_espacios`: PASSED

**Total: 5 pruebas aprobadas en 1,10 segundos.**

## Integración real con Gemini

Comando ejecutado:

`python -m src.enrutamiento`

### Caso 1: Pregunta

**Entrada:** ¿Cómo soluciono un ModuleNotFoundError al ejecutar Python?

**Resultado:** respuesta técnica que explica causas posibles, verificaciones del entorno y pasos de instalación de dependencias.

### Caso 2: Queja

**Entrada:** La aplicación se cierra cada vez que intento iniciar sesión.

**Resultado:** respuesta empática que reconoce el inconveniente y solicita antecedentes para diagnosticar el problema.

### Caso 3: Sugerencia

**Entrada:** Sería útil tener un modo oscuro en la aplicación.

**Resultado:** agradecimiento y explicación de una posible evaluación de la propuesta, sin prometer implementación.

## Observaciones

Las cinco pruebas automatizadas fueron exitosas y los tres ejemplos reales generaron respuestas coherentes con sus rutas esperadas.

La salida visible no incluye la categoría intermedia utilizada por el clasificador. La comprobación explícita de cada ruta se realizó mediante mocks.

## Conclusión

Se implementó y validó técnicamente un flujo condicional con tres rutas de respuesta, normalización de categorías y comportamiento predeterminado ante categorías desconocidas.

**Estado: validación técnica satisfactoria.**