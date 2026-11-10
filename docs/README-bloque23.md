# Bloque 23 — Supervisión humana y trazabilidad del agente

## Diseño

Se reutilizan las herramientas de diagnóstico Python y consulta Git del Bloque 22. Se añade `reembolso_simulado_con_aprobacion`, que **no realiza reembolsos reales**: permite practicar la supervisión de una operación de riesgo alto con un aprobador inyectable.

La demostración para Windows usa `msvcrt` y un tiempo límite; Linux/macOS usa `select` sobre la entrada estándar. Si falta TTY, vence el plazo o la respuesta no es `s`, la acción se rechaza. Las decisiones aprobadas y rechazadas se almacenan temporalmente en `REGISTRO_APROBACIONES` durante la ejecución. No constituyen una autorización duradera ni una auditoría de producción.

`registrar_traza` genera `trazas_agente_bloque23.jsonl` en UTF-8 con consultas, acciones observables y respuestas finales. No guarda pensamientos privados del modelo. El archivo puede contener texto sensible si el usuario lo proporciona: úsalo solamente con datos de demostración y exclúyelo de Git. `detectar_repeticiones` señala herramientas consecutivas repetidas para revisión humana; no determina que sean errores.

## Comandos

Desde la raíz del repositorio, con `.venv` activado:

```powershell
python -m pytest tests/test_agente_bloque23.py -v
python -m pytest tests/ -v
python -m src.agente_bloque23
python -m src.agente_bloque23 --demo-aprobacion
```

Las pruebas no llaman a Gemini ni realizan operaciones reales. El comando sin parámetros sí usa Gemini y crea un JSONL local. El demo de aprobación no requiere API y ofrece hasta 20 segundos para escribir `s` o `n` en una terminal interactiva. La consola de Windows no usa `select` sobre stdin.

Agrega `trazas_agente_bloque23.jsonl` a `.gitignore` si deseas conservar el log localmente. Si el programa se convierte en servicio, sustituye la consola por un proceso de aprobación autenticado, persistente y con un identificador de solicitud para evitar reutilizar aprobaciones, antes de conectar acciones reales.

## Alcance

La aprobación explícita y su registro corresponden a una **simulación pedagógica**. La lección core también exige que el documento de límites describa exclusivamente herramientas y mecanismos existentes, no funciones imaginadas ni reembolsos reales.
