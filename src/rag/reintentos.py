"""Clasificación de errores de Gemini y reintentos con backoff.

Reutiliza `src.cliente.con_reintento` (Bloque 13): backoff exponencial con jitter
que solo reintenta `TimeoutError`. Aquí se traducen los fallos transitorios a
`ErrorTransitorio` (subclase de TimeoutError) y los de autenticación a
`CredencialesInvalidasError`, que nunca se reintenta.
"""
from __future__ import annotations

import re
from typing import Any, Callable, TypeVar

from src.cliente import con_reintento
from src.rag.errores import CredencialesInvalidasError, ErrorTransitorio

T = TypeVar("T")

CODIGOS_TRANSITORIOS = {408, 429, 500, 502, 503, 504}
CODIGOS_AUTENTICACION = {401, 403}
MARCAS_CLAVE_INVALIDA = ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED", "UNAUTHENTICATED")
NOMBRES_ERRORES_RED = {
    "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "TimeoutException", "RemoteProtocolError", "ConnectionError", "Timeout",
}


def _cadena_causas(error: BaseException):
    vistos = set()
    actual: BaseException | None = error
    while actual is not None and id(actual) not in vistos:
        vistos.add(id(actual))
        yield actual
        actual = actual.__cause__ or actual.__context__


def clasificar_error(error: BaseException) -> str:
    """Devuelve 'autenticacion', 'transitorio' o 'permanente' recorriendo la cadena de causas."""
    for causa in _cadena_causas(error):
        codigo = getattr(causa, "code", None)
        texto = str(causa)
        if isinstance(codigo, int):
            if codigo in CODIGOS_AUTENTICACION or (codigo == 400 and any(m in texto for m in MARCAS_CLAVE_INVALIDA)):
                return "autenticacion"
            if codigo in CODIGOS_TRANSITORIOS:
                return "transitorio"
        if isinstance(causa, (ConnectionError, TimeoutError)) or type(causa).__name__ in NOMBRES_ERRORES_RED:
            return "transitorio"
    if any(m in str(error) for m in MARCAS_CLAVE_INVALIDA):
        return "autenticacion"
    return "permanente"


def resumen_error(error: BaseException, limite: int = 160) -> str:
    """Primera línea útil del error más interno, sin claves (patrón AIza...)."""
    interno = list(_cadena_causas(error))[-1]
    texto = re.sub(r"AIza[0-9A-Za-z_\-]+", "<clave oculta>", str(interno)).splitlines()[0] if str(interno) else ""
    return f"{type(interno).__name__}: {texto[:limite]}"


def traducir_error(funcion: Callable[[], T]) -> Callable[[], T]:
    """Envuelve una llamada a Gemini para que sus errores tengan un tipo accionable."""
    def envoltorio() -> T:
        try:
            return funcion()
        except (CredencialesInvalidasError, ErrorTransitorio):
            raise
        except Exception as error:  # Se reclasifica y se vuelve a lanzar siempre; nunca se silencia.
            tipo = clasificar_error(error)
            if tipo == "autenticacion":
                raise CredencialesInvalidasError(
                    "Gemini rechazó la clave (credencial inválida o sin permiso). Revisa .env; no se reintenta."
                ) from error
            if tipo == "transitorio":
                raise ErrorTransitorio(f"Fallo transitorio de Gemini ({resumen_error(error)})") from error
            raise
    return envoltorio


def llamar_con_reintentos(
    funcion: Callable[[], T], intentos: int = 4, espera_base: float = 4, espera_maxima: float = 60
) -> Any:
    """Aplica la política de reintentos del Bloque 13 solo a fallos transitorios."""
    return con_reintento(traducir_error(funcion), intentos=intentos,
                         espera_base=espera_base, espera_maxima=espera_maxima)
