"""Bloque 15: normalizacion, tokenizacion y conteo de palabras.

Ejecutar desde la raiz: python -m src.pipeline_texto
"""
import re
from collections import Counter


def limpiar_texto(texto: str) -> str:
    """Convierte a minusculas, elimina puntuacion y normaliza espacios."""
    if not isinstance(texto, str):
        raise TypeError(f"limpiar_texto espera str, no {type(texto).__name__}")
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto_limpio: str) -> list[str]:
    """Separa por espacios el texto previamente normalizado."""
    return texto_limpio.split()


def procesar_texto(texto: str) -> list[str]:
    """Aplica limpieza y tokenizacion."""
    return tokenizar(limpiar_texto(texto))


def vectorizar(tokens: list[str]) -> Counter:
    """Representacion de bolsa de palabras: frecuencia de cada token."""
    return Counter(tokens)


def coincidencia_palabras(referencia: str, respuesta: str, *, normalizar: bool = True) -> float:
    """Proporcion de palabras UNICAS de referencia presentes en respuesta.

    No mide significado, orden ni frecuencia. Devuelve 0 si la referencia no
    contiene ninguna palabra. Mantiene el ejemplo del material del Bloque 15.
    """
    ref = procesar_texto(referencia) if normalizar else referencia.split()
    res = procesar_texto(respuesta) if normalizar else respuesta.split()
    palabras_ref = set(ref)
    if not palabras_ref:
        return 0.0
    return len(palabras_ref & set(res)) / len(palabras_ref)


if __name__ == "__main__":
    referencia = "El cielo es azul."
    respuesta = "el cielo es azul"
    print("Texto limpio:", limpiar_texto(referencia))
    print("Tokens:", procesar_texto(referencia))
    print("Vector:", vectorizar(procesar_texto(referencia)))
    print(f"Coincidencia cruda: {coincidencia_palabras(referencia, respuesta, normalizar=False):.1%}")
    print(f"Coincidencia procesada: {coincidencia_palabras(referencia, respuesta):.1%}")
