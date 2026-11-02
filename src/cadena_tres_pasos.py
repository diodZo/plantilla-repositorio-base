"""Bloque 18: asistencia técnica con tres pasos LangChain.

Ejecutar desde la raíz del repositorio:
    python -m src.cadena_tres_pasos
"""
import os
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


def construir_cadena(modelo):
    """Crea la chain sin invocar el modelo; permite inyectar dobles de prueba."""
    clasificacion = PromptTemplate.from_template(
        "Eres un analista de soporte técnico. Lee la consulta y devuelve una ficha "
        "breve con: categoría, problema, información conocida e información faltante. "
        "No inventes datos. Consulta:\n{consulta}"
    )
    redaccion = PromptTemplate.from_template(
        "Eres un asistente técnico. A partir de esta ficha, redacta una respuesta "
        "práctica en español con pasos razonables y preguntas si faltan datos. "
        "No afirmes haber ejecutado cambios ni verificado hechos externos.\n" 
        "Ficha:\n{ficha}"
    )
    revision = PromptTemplate.from_template(
        "Eres un editor técnico. Revisa el siguiente borrador: mejora claridad, "
        "precisión y cortesía, conservando las advertencias e incertidumbres. "
        "Devuelve únicamente la respuesta final.\nBorrador:\n{borrador}"
    )
    return (
        clasificacion | modelo | StrOutputParser()
        | (lambda ficha: {"ficha": ficha})
        | redaccion | modelo | StrOutputParser()
        | (lambda borrador: {"borrador": borrador})
        | revision | modelo | StrOutputParser()
    )


def crear_modelo():
    """Adapta las variables del Gate 1 a las esperadas por LangChain."""
    load_dotenv()
    clave = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    if not clave:
        raise ValueError("Falta una clave: GOOGLE_API_KEY, GEMINI_API_KEY o API_KEY en .env")
    modelo = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")
    return ChatGoogleGenerativeAI(model=modelo, google_api_key=clave, temperature=0)


if __name__ == "__main__":
    consulta = (
        "Al ejecutar python -m src.cliente desde mi entorno virtual recibo "
        "ModuleNotFoundError: No module named dotenv. ¿Cómo lo soluciono?"
    )
    try:
        cadena = construir_cadena(crear_modelo())
        print(cadena.invoke({"consulta": consulta}))
    except (ValueError, Exception) as error:
        print(f"No se pudo completar la cadena: {error}")
        raise SystemExit(1) from error
