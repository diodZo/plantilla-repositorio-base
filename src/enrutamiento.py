"""Bloques 19 y 20: enrutamiento condicional y recuperación ante fallos.

Ejecutar desde la raíz del repositorio: python -m src.enrutamiento
"""

import logging
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

PLANTILLA_CLASIFICACION = PromptTemplate.from_template(
    "Clasifica este mensaje de soporte en una sola palabra: "
    "pregunta, queja o sugerencia. Responde solo con esa palabra.\n\n{mensaje}"
)

RESPUESTA_QUEJA_RESPALDO = (
    "Gracias por contarnos el problema. No pudimos analizar tu queja "
    "en este momento. Guarda los detalles del error e inténtalo más tarde "
    "o contacta al equipo de soporte disponible."
)
RESPUESTA_GENERAL_RESPALDO = (
    "No pudimos procesar tu mensaje en este momento. Inténtalo de nuevo más tarde."
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


def construir_cadena_queja_segura(cadena_queja):
    """Respaldo del paso de queja, inyectable para pruebas sin API."""
    respuesta_generica = RunnableLambda(lambda entrada: RESPUESTA_QUEJA_RESPALDO)
    return cadena_queja.with_fallbacks([respuesta_generica])


def construir_cadena(modelo):
    """Montar el flujo seguro sin ejecutar llamadas a la API."""
    pregunta, queja, sugerencia = construir_rutas(modelo)
    return construir_cadena_con_enrutamiento(
        paso_clasificacion=construir_paso_clasificacion(modelo),
        cadena_queja=construir_cadena_queja_segura(queja),
        cadena_sugerencia=sugerencia,
        cadena_pregunta=pregunta,
    )


def procesar_mensaje_seguro(cadena, mensaje):
    """Protección general para fallos no recuperados en clasificación o rutas."""
    try:
        return cadena.invoke({"mensaje": mensaje})
    except Exception:
        logger.exception("Error al procesar mensaje con la cadena orquestada")
        return RESPUESTA_GENERAL_RESPALDO


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
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
        print(procesar_mensaje_seguro(cadena, mensaje))


if __name__ == "__main__":
    main()
