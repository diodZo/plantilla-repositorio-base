
import time
from typing import Callable, Any

from src.consumir_gemini import (
    armar_peticion,
    enviar_peticion,
    extraer_texto
)


def es_error_transitorio(error: Exception) -> bool:
    """Identifica errores que permiten reintentar."""
    mensaje = str(error).lower()

    return (
        "error 429" in mensaje
        or "error 500" in mensaje
        or "error 502" in mensaje
        or "error 503" in mensaje
        or "error 504" in mensaje
        or "no respondió" in mensaje
    )


def con_reintento(
    funcion: Callable[[], Any],
    intentos: int = 3,
    espera_segundos: int = 2
) -> Any:
    """Reintenta solamente ante errores transitorios."""

    if intentos < 1:
        raise ValueError("Debe existir al menos un intento.")

    for intento in range(1, intentos + 1):
        try:
            return funcion()

        except RuntimeError as error:
            if not es_error_transitorio(error):
                raise

            if intento == intentos:
                raise RuntimeError(
                    "El servicio no respondió tras varios intentos. "
                    "Intenta más tarde."
                ) from error

            print(
                f"Intento {intento}/{intentos} falló. "
                f"Reintentando en {espera_segundos} segundos..."
            )

            time.sleep(espera_segundos)


def consultar_modelo(
    pregunta: str,
    system_instruction: str = ""
) -> str:
    """Interfaz pública para consultar Gemini."""

    url, encabezados, cuerpo = armar_peticion(pregunta)

    if system_instruction:
        cuerpo["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    respuesta = con_reintento(
        lambda: enviar_peticion(url, encabezados, cuerpo)
    )

    return extraer_texto(respuesta)


if __name__ == "__main__":
    try:
        resultado = consultar_modelo(
            "¿Cuál es la capital de Chile?"
        )
        print("Respuesta:", resultado)

    except (ValueError, RuntimeError) as error:
        print("Error:", error)
