"""Recuperación híbrida: vectorial (Chroma) + léxica (BM25) fusionadas con Reciprocal Rank Fusion.

RRF: puntaje(d) = Σ_r 1 / (k_rrf + rango_r(d)), con rangos desde 1. Solo usa
posiciones, por lo que no mezcla escalas incompatibles (distancia coseno vs. BM25).
El puntaje RRF no es una probabilidad ni un porcentaje.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from src.rag.configuracion import K_POR_DEFECTO
from src.rag.lexico import IndiceBM25
from src.rag.recuperador import _validar_consulta, buscar_con_score

K_RRF = 60
CANDIDATOS_POR_DEFECTO = 20


@dataclass
class ResultadoHibrido:
    documento: Document
    puntaje_rrf: float
    rango_vectorial: int | None = None
    distancia: float | None = None
    rango_lexico: int | None = None
    puntaje_bm25: float | None = None


def fusionar_rrf(
    vectoriales: list[tuple[Document, float]],
    lexicos: list[tuple[Document, float]],
    k: int,
    k_rrf: int = K_RRF,
) -> list[ResultadoHibrido]:
    """Fusiona dos rankings, deduplica por ID de chunk y conserva los metadatos."""
    if k < 1 or k_rrf < 1:
        raise ValueError("k y k_rrf deben ser enteros >= 1.")
    resultados: dict[str, ResultadoHibrido] = {}
    for nombre, ranking in (("vectorial", vectoriales), ("lexico", lexicos)):
        vistos: set[str] = set()
        rango = 0
        for documento, valor in ranking:
            if not documento.id:
                raise ValueError("No se puede fusionar un documento sin ID de chunk.")
            if documento.id in vistos:
                continue  # duplicado dentro del mismo ranking: cuenta una vez
            vistos.add(documento.id)
            rango += 1
            actual = resultados.setdefault(documento.id, ResultadoHibrido(documento, 0.0))
            actual.puntaje_rrf += 1.0 / (k_rrf + rango)
            if nombre == "vectorial":
                actual.rango_vectorial, actual.distancia = rango, float(valor)
            else:
                actual.rango_lexico, actual.puntaje_bm25 = rango, float(valor)
    ordenados = sorted(resultados.values(), key=lambda r: (-r.puntaje_rrf, r.documento.id))
    return ordenados[:k]


def buscar_hibrido(
    almacen,
    pregunta: str,
    k: int = K_POR_DEFECTO,
    candidatos_vectoriales: int = CANDIDATOS_POR_DEFECTO,
    candidatos_lexicos: int = CANDIDATOS_POR_DEFECTO,
    k_rrf: int = K_RRF,
    indice_lexico: IndiceBM25 | None = None,
) -> list[ResultadoHibrido]:
    """Una sola llamada a `embed_query`; la parte léxica usa los textos persistidos."""
    _validar_consulta(pregunta, k)
    if candidatos_vectoriales < 1 or candidatos_lexicos < 1:
        raise ValueError("La cantidad de candidatos debe ser >= 1.")
    vectoriales = buscar_con_score(almacen, pregunta, max(k, candidatos_vectoriales))
    indice = indice_lexico or IndiceBM25.desde_almacen(almacen)
    lexicos = [(r.documento, r.puntaje) for r in indice.buscar(pregunta, max(k, candidatos_lexicos))]
    return fusionar_rrf(vectoriales, lexicos, k, k_rrf)
