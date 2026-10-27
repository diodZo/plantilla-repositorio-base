"""Cliente modular Gemini — Bloque 13.

Ejecutar desde la raíz: python -m src.cliente
Conserva intacto el módulo original del Gate 1.
"""
import random
import time
from typing import Any, Callable

import requests
from src.consumir_gemini import armar_peticion, extraer_texto

# Tarifa ilustrativa del material del Bloque 13 (NO es precio oficial de Gemini).
# Para una estimación real, diferenciar tarifas de entrada y salida.
COSTO_POR_1000_TOKENS = 0.002
costo_total_sesion = 0.0


def enviar_peticion(url: str, encabezados: dict, cuerpo: dict) -> dict:
    """Clasifica errores de API como permanentes o recuperables."""
    try:
        respuesta = requests.post(url, headers=encabezados, json=cuerpo, timeout=30)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
        raise TimeoutError("No se pudo contactar a Gemini; fallo temporal de red.") from error

    if respuesta.status_code in (401, 403):
        raise ValueError("Credencial inválida o sin permiso. Revisa API_KEY.")
    if respuesta.status_code == 429 or respuesta.status_code >= 500:
        raise TimeoutError(f"Gemini respondió HTTP {respuesta.status_code}; error temporal o cuota excedida.")
    try:
        respuesta.raise_for_status()
        return respuesta.json()
    except requests.exceptions.HTTPError as error:
        raise RuntimeError(f"Petición HTTP no recuperable: {respuesta.status_code}") from error
    except ValueError as error:
        raise RuntimeError("Gemini devolvió una respuesta JSON inválida.") from error


def con_reintento(
    funcion: Callable[[], Any],
    intentos: int = 3,
    espera_base: float = 2,
    espera_maxima: float = 30,
) -> Any:
    """Backoff exponencial con jitter; nunca reintenta errores de credencial."""
    if intentos < 1 or espera_base < 0 or espera_maxima < 0:
        raise ValueError("Parámetros de reintento inválidos.")
    for intento in range(1, intentos + 1):
        try:
            return funcion()
        except TimeoutError:
            if intento == intentos:
                raise
            espera = min(espera_base * (2 ** (intento - 1)), espera_maxima)
            pausa = espera + random.uniform(0, espera * 0.1)
            print(f"Intento {intento}/{intentos} falló. Reintentando en {pausa:.1f}s...")
            time.sleep(pausa)


def registrar_costo(respuesta: dict) -> float:
    """Costo referencial basado en totalTokenCount y acumulado por sesión."""
    global costo_total_sesion
    uso = respuesta.get("usageMetadata", {})
    total_tokens = uso.get("totalTokenCount", 0)
    costo_estimado = (total_tokens / 1000) * COSTO_POR_1000_TOKENS
    costo_total_sesion += costo_estimado
    print(f"Operación: {total_tokens} tokens; costo referencial: USD {costo_estimado:.6f}; acumulado: USD {costo_total_sesion:.6f}")
    return costo_estimado


def consultar_modelo(pregunta: str, system_instruction: str = "") -> str:
    """Interfaz pública: petición, reintentos, costo y texto."""
    url, encabezados, cuerpo = armar_peticion(pregunta)
    if system_instruction:
        cuerpo["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    try:
        respuesta = con_reintento(lambda: enviar_peticion(url, encabezados, cuerpo))
    except TimeoutError as error:
        raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.") from error
    registrar_costo(respuesta)
    return extraer_texto(respuesta)


if __name__ == "__main__":
    try:
        print("Respuesta:", consultar_modelo("¿Cuál es la capital de Chile?"))
        print(f"Costo referencial acumulado: USD {costo_total_sesion:.6f}")
    except (ValueError, RuntimeError) as error:
        print("Error:", error)
