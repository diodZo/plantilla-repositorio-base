"""Evaluación offline de comportamiento (Bloque 29): checks deterministas sobre respuestas.

Compara respuestas (texto) con las salidas de referencia del conjunto de validación. Mide
estructura JSON, claves exactas, categoría válida, coherencia de la acción y coincidencia de
categoría. NO es la "exactitud de un modelo entrenado": solo describe las respuestas que se le den.
El campo `origen` indica de dónde salen (p. ej. "control_referencia" o "gemini_base").
"""
from __future__ import annotations

import json
from typing import Any

from src.personalizacion.dataset import CATEGORIAS, categoria_de
from src.personalizacion.validacion import revisar_coherencia, validar_salida

CHECKS = ("json_valido", "claves_exactas", "categoria_valida", "accion_coherente", "categoria_coincide")
CODIGOS_ESTRUCTURA = {"tipo_salida", "salida_vacia", "json_malformado", "json_no_objeto"}
CODIGOS_CLAVES = {"clave_faltante", "clave_inesperada"}


def evaluar_respuesta(respuesta: Any, referencia: dict) -> dict[str, Any]:
    datos, fallos = validar_salida(respuesta, CATEGORIAS)
    codigos = {c for c, _ in fallos}
    json_valido = datos is not None and not (codigos & CODIGOS_ESTRUCTURA)
    claves_exactas = json_valido and not (codigos & CODIGOS_CLAVES)
    categoria_valida = json_valido and isinstance(datos.get("categoria"), str) and datos["categoria"] in CATEGORIAS
    accion = datos.get("accion_sugerida") if json_valido else None
    accion_coherente = bool(categoria_valida and isinstance(accion, str) and accion.strip()
                            and not revisar_coherencia(datos["categoria"], accion)[0])
    categoria_coincide = bool(categoria_valida and datos["categoria"] == categoria_de(referencia))
    return {
        "json_valido": json_valido,
        "claves_exactas": claves_exactas,
        "categoria_valida": categoria_valida,
        "accion_coherente": accion_coherente,
        "categoria_coincide": categoria_coincide,
        "fallos": [f"{c}: {m}" for c, m in fallos],
    }


def evaluar_respuestas(referencias: list[dict], respuestas: list[Any], origen: str) -> dict[str, Any]:
    """Aplica los checks a cada par (referencia, respuesta). Exige la misma cantidad de ambos."""
    if len(referencias) != len(respuestas):
        raise ValueError(f"Hay {len(referencias)} referencias y {len(respuestas)} respuestas; deben coincidir.")
    detalle = [evaluar_respuesta(r, ref) for ref, r in zip(referencias, respuestas)]
    n = len(detalle)
    tasas = {check: (sum(d[check] for d in detalle) / n if n else None) for check in CHECKS}
    incumplen_formato = sum(1 for d in detalle if not d["claves_exactas"])
    return {
        "tipo": "checks_deterministas_offline",
        "origen": origen,
        "n": n,
        "tasas": tasas,
        "incumplimiento_formato": (incumplen_formato / n) if n else None,
        "detalle": detalle,
    }


def respuestas_de_referencia(referencias: list[dict]) -> list[str]:
    """Control de referencia: las propias salidas esperadas (debe dar 100 %; verifica el evaluador, no un modelo)."""
    return [r["salida"] for r in referencias]


def cargar_respuestas(ruta) -> list[Any]:
    """Archivo JSON con una lista de textos de respuesta, en el mismo orden que la validación."""
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if isinstance(datos, dict) and "respuestas" in datos:
        datos = datos["respuestas"]
    if not isinstance(datos, list):
        raise ValueError(f"{ruta} debe contener una lista de respuestas o {{'respuestas': [...]}}.")
    return datos
