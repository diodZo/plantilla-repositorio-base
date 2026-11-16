"""Tokens reales y costos estimados del flujo RAG (Bloque 28).

Tres categorías que nunca se mezclan:
- `calculado`: tokens reportados por el proveedor × tarifa verificada. Sigue siendo una
  ESTIMACIÓN del cargo: la facturación real depende del nivel (gratuito o de pago),
  descuentos, caché y redondeos.
- `estimado`: tokens aproximados (p. ej., caracteres/4) cuando el proveedor no los reporta.
- `desconocido`: faltan tokens o tarifa; se registra None con el motivo.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from src.rag.configuracion import RAIZ_REPO

ARCHIVO_TARIFAS = RAIZ_REPO / "data" / "tarifas_gemini.json"
CARACTERES_POR_TOKEN_ESTIMADO = 4


def _validar_no_negativo(valor, nombre: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0 or math.isnan(valor):
        raise ValueError(f"{nombre} debe ser un número no negativo; se recibió {valor!r}.")


def costo_por_tokens(tokens: int | None, tarifa_por_millon: float | None) -> float | None:
    """tokens × tarifa / 1 000 000. None si falta alguno de los dos."""
    if tokens is None or tarifa_por_millon is None:
        return None
    _validar_no_negativo(tokens, "tokens")
    _validar_no_negativo(tarifa_por_millon, "tarifa")
    return tokens * tarifa_por_millon / 1_000_000


def calcular_costo(tokens_entrada, tokens_salida, tarifa_entrada_por_millon, tarifa_salida_por_millon) -> float | None:
    """Costo = entrada × tarifa_entrada / 1e6 + salida × tarifa_salida / 1e6 (USD).

    Devuelve None si falta cualquier dato: un costo parcial no se presenta como total.
    """
    entrada = costo_por_tokens(tokens_entrada, tarifa_entrada_por_millon)
    salida = costo_por_tokens(tokens_salida, tarifa_salida_por_millon)
    if entrada is None or salida is None:
        return None
    return entrada + salida


@dataclass(frozen=True)
class Tarifa:
    modelo: str
    entrada: float | None
    salida: float | None
    fuente: str
    fecha_consulta: str
    tipo: str  # "verificada" o "ilustrativa"


def cargar_tarifas(ruta: Path = ARCHIVO_TARIFAS) -> dict[str, Tarifa]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if datos.get("tipo") not in ("verificada", "ilustrativa"):
        raise ValueError("El archivo de tarifas debe declarar tipo 'verificada' o 'ilustrativa'.")
    if not datos.get("fuente") or not datos.get("fecha_consulta"):
        raise ValueError("El archivo de tarifas debe indicar 'fuente' y 'fecha_consulta'.")
    tarifas = {}
    for modelo, valores in datos.get("modelos", {}).items():
        for clave in ("entrada", "salida"):
            if valores.get(clave) is not None:
                _validar_no_negativo(valores[clave], f"tarifa {clave} de {modelo}")
        tarifas[modelo] = Tarifa(modelo, valores.get("entrada"), valores.get("salida"),
                                 datos["fuente"], datos["fecha_consulta"], datos["tipo"])
    return tarifas


def buscar_tarifa(tarifas: dict[str, Tarifa], modelo: str) -> Tarifa | None:
    """Acepta el nombre con o sin el prefijo 'models/'."""
    return tarifas.get(modelo) or tarifas.get(modelo.removeprefix("models/")) or tarifas.get(f"models/{modelo}")


def extraer_uso(mensaje) -> dict:
    """Tokens reportados por Gemini en `usage_metadata` de LangChain; None si no vienen.

    En langchain-google-genai 4.4.2: input = prompt (+ herramientas); output = candidatos +
    razonamiento; total = total_token_count de la API. `otros` es total - input - output,
    solo si los tres existen (no se asume que sea 0).
    """
    uso = getattr(mensaje, "usage_metadata", None)
    if not uso:
        return {"estado": "no_disponible", "entrada": None, "salida": None, "total": None,
                "razonamiento": None, "cache_lectura": None, "otros": None}
    entrada, salida, total = uso.get("input_tokens"), uso.get("output_tokens"), uso.get("total_tokens")
    return {
        "estado": "reportado",
        "entrada": entrada,
        "salida": salida,
        "total": total,
        "razonamiento": (uso.get("output_token_details") or {}).get("reasoning"),
        "cache_lectura": (uso.get("input_token_details") or {}).get("cache_read"),
        "otros": (total - entrada - salida) if None not in (entrada, salida, total) else None,
    }


def estimar_tokens_por_caracteres(texto: str) -> int:
    """Aproximación grosera (caracteres/4). NO son tokens reales."""
    return math.ceil(len(texto) / CARACTERES_POR_TOKEN_ESTIMADO)


def desglose_costo(uso_generacion: dict, tarifa_generacion: Tarifa | None,
                   texto_consulta: str, tarifa_embedding: Tarifa | None) -> dict:
    """Costo de generación (calculado o desconocido) y del embedding de consulta (estimado)."""
    no_incluidos = ["importe facturado (depende del nivel gratuito/de pago, caché y descuentos)"]
    if tarifa_generacion is None:
        costo_generacion, entrada, salida, estado_gen = None, None, None, "desconocido: modelo sin tarifa configurada"
    elif uso_generacion.get("estado") != "reportado":
        costo_generacion, entrada, salida, estado_gen = None, None, None, "desconocido: tokens no reportados"
    else:
        entrada = costo_por_tokens(uso_generacion["entrada"], tarifa_generacion.entrada)
        salida = costo_por_tokens(uso_generacion["salida"], tarifa_generacion.salida)
        costo_generacion = calcular_costo(uso_generacion["entrada"], uso_generacion["salida"],
                                          tarifa_generacion.entrada, tarifa_generacion.salida)
        estado_gen = f"calculado (tokens reales × tarifa {tarifa_generacion.tipo})" if costo_generacion is not None \
            else "desconocido: falta un conteo de tokens"
        if uso_generacion.get("cache_lectura"):
            no_incluidos.append("descuento por tokens en caché (la entrada se calculó a tarifa completa)")
    tokens_emb_estimados = estimar_tokens_por_caracteres(texto_consulta)
    costo_emb = costo_por_tokens(tokens_emb_estimados, tarifa_embedding.entrada) if tarifa_embedding else None
    no_incluidos.append("embedding de consulta: el proveedor no reporta tokens; su costo se muestra aparte como estimación")
    return {
        "generacion": {"entrada_usd": entrada, "salida_usd": salida, "total_usd": costo_generacion, "estado": estado_gen},
        "embedding_consulta": {"tokens_estimados": tokens_emb_estimados, "metodo": f"caracteres/{CARACTERES_POR_TOKEN_ESTIMADO}",
                               "costo_estimado_usd": costo_emb,
                               "estado": "estimado" if costo_emb is not None else "desconocido: sin tarifa"},
        "total_conocido_usd": costo_generacion,
        "no_incluido": no_incluidos,
    }
