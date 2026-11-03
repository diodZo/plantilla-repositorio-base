"""Bloque 19: enrutamiento condicional de mensajes de soporte con LangChain.

Ejecución desde la raíz del repositorio: python -m src.enrutamiento
"""

import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI


PLANTILLA_CLASIFICACION = PromptTemplate.from_template(
    "Clasifica este mensaje de soporte en una sola palabra: "
    "pregunta, queja o sugerencia. Responde solo con esa palabra.\n\n{mensaje}"
)


def construir_paso_clasificacion(modelo):
    """Clasificar el mensaje y normalizar espacios y mayúsculas."""
    return (
        PLANTILLA_CLASIFICACION
        | modelo
        | StrOutputParser()
        | (lambda texto: texto.strip().lower())
    )


def construir_rutas(modelo):
    """Crear tres respuestas distintas, una por categoría."""
    cadena_pregunta = (
        PromptTemplate.from_template(
            "Responde esta pregunta técnica con precisión. "
            "Si falta información, solicítala; no inventes pasos específicos "
            "de un producto desconocido.\n\n{mensaje}"
        )
        | modelo
        | StrOutputParser()
    )
    cadena_queja = (
        PromptTemplate.from_template(
            "Responde a esta queja con empatía, reconoce el problema y "
            "propón pasos prudentes para investigarlo. No prometas acciones "
            "que no puedas realizar.\n\n{mensaje}"
        )
        | modelo
        | StrOutputParser()
    )
    cadena_sugerencia = (
        PromptTemplate.from_template(
            "Agradece esta sugerencia y explica que puede evaluarse. "
            "No prometas que se implementará.\n\n{mensaje}"
        )
        | modelo
        | StrOutputParser()
    )
    return cadena_pregunta, cadena_queja, cadena_sugerencia


def construir_cadena_con_enrutamiento(
    paso_clasificacion,
    cadena_queja=None,
    cadena_sugerencia=None,
    cadena_pregunta=None,
):
    """Conservar el mensaje, agregar la categoría y elegir una ruta.

    La ruta pregunta es la predeterminada, incluso para categorías no reconocidas,
    de acuerdo con el ejemplo del material del Bloque 19.
    """
    bifurcacion = RunnableBranch(
        (lambda x: x["categoria"] == "queja", cadena_queja if cadena_queja is not None else RunnablePassthrough()),
        (lambda x: x["categoria"] == "sugerencia", cadena_sugerencia if cadena_sugerencia is not None else RunnablePassthrough()),
        cadena_pregunta if cadena_pregunta is not None else RunnablePassthrough(),
    )
    return RunnablePassthrough.assign(categoria=paso_clasificacion) | bifurcacion


def construir_cadena(modelo):
    """Montar el flujo con inyección del modelo, sin realizar llamadas a la API."""
    pregunta, queja, sugerencia = construir_rutas(modelo)
    return construir_cadena_con_enrutamiento(
        paso_clasificacion=construir_paso_clasificacion(modelo),
        cadena_queja=queja,
        cadena_sugerencia=sugerencia,
        cadena_pregunta=pregunta,
    )


def main():
    load_dotenv()
    # Compatibilidad con API_KEY del cliente previo y nombres del conector.
    clave = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    if not clave:
        raise RuntimeError("Configura API_KEY, GEMINI_API_KEY o GOOGLE_API_KEY en .env")

    nombre_modelo = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
    modelo = ChatGoogleGenerativeAI(model=nombre_modelo, google_api_key=clave)
    cadena = construir_cadena(modelo)

    ejemplos = (
        "¿Cómo soluciono un ModuleNotFoundError al ejecutar Python?",
        "La aplicación se cierra cada vez que intento iniciar sesión.",
        "Sería útil tener un modo oscuro en la aplicación.",
    )
    for numero, mensaje in enumerate(ejemplos, start=1):
        print(f"\n--- CASO {numero} ---\nMensaje: {mensaje}")
        print(cadena.invoke({"mensaje": mensaje}))


if __name__ == "__main__":
    main()
