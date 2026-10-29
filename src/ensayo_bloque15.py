"""Ensayo de tres respuestas REALES de Gemini para el Bloque 15.

Ejecutar desde la raiz del repositorio: python -m src.ensayo_bloque15
Requiere .env configurado; consume cuota de API y puede tener costo.
"""
from datetime import datetime, timezone
from pathlib import Path

from src.cliente import consultar_modelo
from src.pipeline_texto import coincidencia_palabras

CASOS = [
    ("¿Cuál es la capital de Chile? Responde con una oración breve.", "La capital de Chile es Santiago."),
    ("¿Qué es Python? Responde con una oración breve.", "Python es un lenguaje de programación."),
    ("¿Qué es una API? Responde con una oración breve.", "Una API permite la comunicación entre aplicaciones."),
]


def ejecutar_ensayo() -> None:
    registro = [
        "# Ensayo Bloque 15 — resultados reales",
        "",
        f"Fecha UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "Métrica: proporción de palabras únicas de referencia presentes en la respuesta.",
        "No evalúa significado ni calidad semántica.",
        "",
    ]
    for numero, (consulta, referencia) in enumerate(CASOS, start=1):
        try:
            respuesta = consultar_modelo(consulta)
        except (RuntimeError, ValueError) as error:
            registro.extend([f"## Caso {numero}", "", f"Error: {error}", ""])
            print(f"Caso {numero}: ERROR — {error}")
            continue
        cruda = coincidencia_palabras(referencia, respuesta, normalizar=False)
        procesada = coincidencia_palabras(referencia, respuesta, normalizar=True)
        registro.extend([
            f"## Caso {numero}", "", f"**Pregunta:** {consulta}", "",
            f"**Referencia:** {referencia}", "", f"**Respuesta real:** {respuesta}", "",
            f"**Coincidencia cruda:** {cruda:.1%}", "",
            f"**Coincidencia procesada:** {procesada:.1%}", "",
        ])
        print(f"Caso {numero}: cruda {cruda:.1%} | procesada {procesada:.1%}")
    ruta = Path("docs/ensayo-bloque15.md")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(registro), encoding="utf-8")
    print(f"Registro guardado en: {ruta}")


if __name__ == "__main__":
    ejecutar_ensayo()
