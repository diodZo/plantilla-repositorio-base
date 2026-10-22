# Gate 1 — Registro de ensayo de instalación limpia

- **Fecha del registro:** 22 de octubre de 2026 (fecha de documentación; la salida compartida no muestra fecha de ejecución).
- **Sistema operativo:** Windows (PowerShell; versión exacta no registrada).
- **Python:** Entorno con paquetes `cp313` en la instalación; confirmar versión exacta con `python --version`.
- **Ruta de ensayo:** `D:\Repositorios\curso\evidencia\prueba-gate1`.
- **Modelo utilizado:** No aparece en la salida de consola; comprobar `AI_MODEL` localmente sin exponer `API_KEY`.
- **Repositorio:** `https://github.com/diodZo/plantilla-repositorio-base`.

## Procedimiento y resultados observados

| Verificación | Resultado | Evidencia |
|---|---|---|
| Creación de entorno virtual | **Correcto** | `py -m venv venv` y activación `venv\Scripts\Activate.ps1` sin errores visibles. |
| Instalación desde `requirements.txt` | **Correcto** | `pip` informó `Successfully installed`, incluyendo `python-dotenv==1.2.4` y `requests==2.34.2`. |
| Copia de configuración | **Correcto** | `Copy-Item .env.example .env` se ejecutó sin errores visibles. |
| Consumo real de Gemini | **Correcto** | `python -m src.consumir_gemini` devolvió una definición de API. |
| Clasificación de sentimiento | **3/3** | Los tres intentos indicaron `exito`. |
| Extracción de entidades | **3/3** | Los tres intentos indicaron `exito`. |
| Resumen corto | **3/3** | Los tres intentos indicaron `exito`. |
| Registro de resultados | **Creado** | La consola informó escritura en `prompts/registro_resultados.json` de la copia de ensayo. |
| Exclusión de `.env` | **Correcto en archivos rastreados** | `git ls-files .env` no devolvió salida. |
| Historial de `.env` | **Sin coincidencias en la ruta consultada** | `git log --all --oneline -- .env` no devolvió salida. |

**Resultado de validación estructurada:** 9 de 9 intentos informados como exitosos (100 % en esta ejecución). Esto no garantiza consistencia del 100 % en futuras ejecuciones.

## Extractos de evidencia

```text
Successfully installed ... python-dotenv-1.2.4 requests-2.34.2 ...

> python -m src.consumir_gemini
Una API es un conjunto de reglas y protocolos que permite que dos aplicaciones diferentes se comuniquen e intercambien datos entre sí.

clasificar_sentimiento: 3/3 respuestas válidas
extraer_entidades: 3/3 respuestas válidas
resumen_corto: 3/3 respuestas válidas

> git ls-files .env
[sin salida]
> git log --all --oneline -- .env
[sin salida]
```

## Observaciones y límites

- La salida compartida no incluye el comando de clonación ni su resultado: la ruta `prueba-gate1` es consistente con una copia de ensayo, pero la clonación **no queda demostrada** por esta transcripción.
- No se incluye `python --version` ni `git rev-parse --short HEAD`; conviene registrarlos para reproducibilidad y trazabilidad.
- El script de consistencia modifica `prompts/registro_resultados.json` dentro de la copia de prueba. No es necesario incorporar ese cambio desde el clon de ensayo a menos que se desee conservar la nueva evidencia.
- No se observan claves secretas en la transcripción. Los comandos ejecutados descartan que `.env` esté rastreado en la versión local o en la historia consultada por ruta, pero no equivalen a una auditoría exhaustiva de todos los archivos del historial.

## Conclusión

**Ensayo funcional satisfactorio en los pasos observados.** La instalación de dependencias, el consumo real de la API y las nueve validaciones JSON finalizaron correctamente. La exclusión de `.env` también pasó las verificaciones mostradas. Antes de presentar el Gate 1, registrar el commit probado y confirmar que la copia procede de una clonación limpia. No se atribuye una aprobación formal del Gate: corresponde a Skillnest.
