# Gate 1 — Registro de ensayo de instalación limpia

> **Estado: pendiente de ejecución.** Completa este documento únicamente con resultados observados. No lo marques aprobado antes de hacer el ensayo.

- **Fecha del ensayo:** Pendiente
- **Sistema operativo y versión:** Pendiente
- **Versión de Python (`python --version`):** Pendiente
- **Commit o rama probada (`git rev-parse --short HEAD`):** Pendiente
- **Modelo configurado (sin incluir API Key):** Pendiente

## Procedimiento ejecutado

1. [ ] Cloné el repositorio en una carpeta nueva.
2. [ ] Creé y activé un entorno virtual nuevo.
3. [ ] Instalé las dependencias con `python -m pip install -r requirements.txt`.
4. [ ] Copié `.env.example` a `.env` y configuré una credencial local válida.
5. [ ] Ejecuté `python -m src.consumir_gemini`.
6. [ ] Verifiqué una respuesta real de Gemini, no solo ausencia de traceback.
7. [ ] Ejecuté `python -m prompts.test_consistencia --repeticiones 3 --espera 3 --reintentos 2`.
8. [ ] Comprobé que `git ls-files .env` no devuelve entradas.
9. [ ] Comprobé que `git log --all --oneline -- .env` no devuelve entradas.

## Evidencia

| Verificación | Resultado real | Observaciones |
| --- | --- | --- |
| Instalación de dependencias | Pendiente | |
| Ejecución de la miniaplicación | Pendiente | |
| Consistencia JSON | Pendiente | Registrar éxitos/intentos y el modelo |
| Exclusión de `.env` | Pendiente | |
| Revisión del historial de `.env` | Pendiente | |

## Hallazgos y correcciones

Pendiente de completar tras el ensayo.

## Conclusión

**Pendiente:** no afirmar que el entorno es reproducible ni que el Gate está aprobado hasta verificar la instalación y ejecución reales.
