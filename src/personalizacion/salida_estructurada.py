"""Línea base Prompt + Pydantic (Bloque 30): alternativa práctica antes de invertir en tuning.

Se construye LOCALMENTE: un esquema Pydantic estricto, un prompt con pocos ejemplos tomados del
dataset de entrenamiento y la `GenerateContentConfig` de salida estructurada de google-genai.
Este módulo no llama a Gemini; su tasa real de incumplimiento queda pendiente de medir.
"""
from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.personalizacion.dataset import CATEGORIAS

Categoria = Literal["red", "autenticacion", "cuota", "entorno", "consistencia_indice"]


class SalidaClasificacion(BaseModel):
    """Contrato de salida: exactamente `categoria` y `accion_sugerida`."""

    model_config = ConfigDict(extra="forbid", strict=True)

    categoria: Categoria
    accion_sugerida: str = Field(min_length=1)

    @field_validator("accion_sugerida")
    @classmethod
    def _no_vacia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("accion_sugerida no puede estar en blanco")
        return valor


if set(get_args(Categoria)) != set(CATEGORIAS):  # El Literal y el catálogo deben coincidir.
    raise RuntimeError("Las categorías del esquema Pydantic no coinciden con CATEGORIAS.")

INSTRUCCION_SISTEMA = (
    "Clasificas mensajes de error técnicos del proyecto. Responde SOLO con un objeto JSON con las claves "
    f"'categoria' (una de: {', '.join(CATEGORIAS)}) y 'accion_sugerida' (texto breve en español). "
    "Los errores de credencial (400 API_KEY_INVALID, 401, 403 o clave ausente) nunca se reintentan. "
    "Los fallos de red y 5xx se reintentan con backoff exponencial. Los 429 son de cuota."
)


def construir_prompt(mensaje_error: str, ejemplos: list[dict] | None = None, max_ejemplos: int = 5) -> str:
    """Prompt few-shot: reutiliza ejemplos del dataset sin entrenar nada."""
    partes = []
    for ejemplo in (ejemplos or [])[:max_ejemplos]:
        partes.append(f"Error: {ejemplo['entrada']}\nJSON: {ejemplo['salida']}")
    partes.append(f"Error: {mensaje_error}\nJSON:")
    return "\n\n".join(partes)


def construir_config_generacion():
    """`GenerateContentConfig` con salida JSON restringida al esquema. Solo construye el objeto."""
    from google.genai import types

    return types.GenerateContentConfig(
        system_instruction=INSTRUCCION_SISTEMA,
        response_mime_type="application/json",
        response_schema=SalidaClasificacion,
    )


def parsear_respuesta(texto: str) -> SalidaClasificacion:
    """Valida el texto devuelto por el modelo. Lanza `ValidationError` si no cumple el contrato."""
    return SalidaClasificacion.model_validate_json(texto)


def es_valida(texto: str) -> bool:
    try:
        parsear_respuesta(texto)
    except ValidationError:
        return False
    return True
