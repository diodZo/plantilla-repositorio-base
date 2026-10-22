# Miniaplicación Python — Google Gemini

Proyecto de la **Especialización en Desarrollo con IA Generativa**. Consume la API REST de Gemini, maneja fallos de solicitud y valida respuestas JSON estructuradas mediante un banco de prompts reutilizable.

## Requisitos

- Python 3.10 o superior (recomendado para ejecutar los scripts del banco de prompts).
- Git y conexión a internet.
- Una API Key de Gemini con cuota disponible y acceso al modelo configurado.

## Instalación desde cero

```powershell
git clone https://github.com/diodZo/plantilla-repositorio-base.git
cd plantilla-repositorio-base
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

En macOS/Linux sustituye la activación por `source venv/bin/activate` y copia con `cp .env.example .env`. Si corresponde usa `python3` en vez de `python`.

Edita `.env` (no `.env.example`) con tus valores privados:

```dotenv
API_KEY=tu_clave_privada_de_gemini
AI_MODEL=gemini-3.5-flash-lite
```

El identificador del modelo debe existir y estar habilitado para tu API Key. **Nunca compartas el archivo `.env`.** El archivo `.gitignore` lo excluye del control de versiones.

## Ejecutar la miniaplicación

Desde la raíz del repositorio y con el entorno virtual activado:

```powershell
python -m src.consumir_gemini
```

El módulo realiza una pregunta de demostración y muestra el texto generado. Si Gemini no responde, el programa muestra un error controlado. Se necesita cuota disponible para ejecutar la solicitud.

## Banco de prompts y consistencia

El banco en `prompts/banco.py` contiene los casos `clasificar_sentimiento`, `extraer_entidades` y `resumen_corto`, con instrucciones de sistema, ejemplos y esquemas JSON.

```powershell
python -m prompts.test_consistencia --repeticiones 3 --espera 3 --reintentos 2
```

Este comando hace **al menos nueve intentos independientes** contra la API (puede hacer solicitudes adicionales cuando hay reintentos), consume cuota y crea o reemplaza `prompts/registro_resultados.json`. Verifica las claves y los tipos del JSON y conserva los errores de servicio separados de los de estructura. Si recibes un 429 de cuota agotada con una espera larga, detén nuevas ejecuciones hasta que se restablezca o utiliza un modelo habilitado con cuota.

## Estructura principal

```text
src/consumir_gemini.py           Consumo HTTP de Gemini y manejo de errores
src/variables_entorno.py        Comprobación segura de configuración
prompts/banco.py                Tres prompts con esquema de respuesta
prompts/test_consistencia.py    Pruebas repetidas de JSON estructurado
prompts/registro_resultados.json Evidencia de la ejecución real
docs/diagrama_arquitectura.png  Arquitectura de la miniaplicación
docs/decision-arquitectura.md   ADR de selección del modelo
docs/comparacion_modelos.csv    Mediciones de modelos
docs/ensayo-gate1.md            Registro de la instalación limpia
requirements.txt               Dependencias Python
.env.example                   Variables de ejemplo sin secretos
```

**Nota:** `src/main.py` está vacío. El punto de entrada que debes ejecutar es `python -m src.consumir_gemini`.

## Instalación limpia para Gate 1

Clona el repositorio en **otra carpeta**, crea allí un `venv` nuevo, instala únicamente desde `requirements.txt`, configura `.env` a partir de `.env.example` y ejecuta los comandos indicados arriba sin utilizar librerías previamente instaladas. Guarda el resultado real en `docs/ensayo-gate1.md`.

Comprueba también:

```powershell
git status --short
git ls-files .env
git log --all --oneline -- .env
```

Los dos últimos comandos no deberían mostrar ninguna entrada para el archivo `.env`. Si una clave real se filtró en algún commit, revócala/regenérala en Google AI Studio y evalúa limpiar el historial.

## Documentación de la decisión

Ver [diagrama de arquitectura](docs/diagrama_arquitectura.png), [registro de decisión de arquitectura](docs/decision-arquitectura.md) y [resultados comparativos](docs/comparacion_modelos.csv). El cálculo de costos está documentado como medición independiente; no forma parte del flujo principal de `src/consumir_gemini.py`.
