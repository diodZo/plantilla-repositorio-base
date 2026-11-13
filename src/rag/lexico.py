"""Recuperación léxica BM25 (Okapi) sobre los chunks ya persistidos en Chroma.

No calcula embeddings: lee los textos y metadatos con `almacen.get()`.
Normalización: minúsculas, sin tildes, separación por caracteres no alfanuméricos
(también separa `reembolso_simulado_con_aprobacion`), stopwords en español y
stemming por truncamiento a 5 caracteres (`autorice`/`autorización` -> `autor`).
Es una aproximación simple y documentada, no un analizador lingüístico completo.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from langchain_core.documents import Document

LONGITUD_RAIZ = 5
STOPWORDS = frozenset("""
a al algo ante antes asi como con cual cuales cuando de del desde donde el ella ellas ellos en
entre era es esa ese eso esta este esto estos esas esos fue ha hay la las le les lo los mas me mi
muy no nos o otra otro para pero por porque que se si sin sobre su sus tambien te tiene un una uno
unos unas y ya yo the of to and is in on for
""".split())


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def tokenizar(texto: str) -> list[str]:
    return [t[:LONGITUD_RAIZ] for t in re.findall(r"[a-z0-9]+", normalizar(texto))
            if len(t) > 1 and t not in STOPWORDS]


@dataclass
class ResultadoLexico:
    documento: Document
    puntaje: float


class IndiceBM25:
    def __init__(self, documentos: list[Document], k1: float = 1.5, b: float = 0.75):
        if any(not d.id for d in documentos):
            raise ValueError("Todos los documentos del índice léxico necesitan ID.")
        self.documentos = documentos
        self.k1, self.b = k1, b
        self.frecuencias = [Counter(tokenizar(d.page_content)) for d in documentos]
        self.longitudes = [sum(f.values()) for f in self.frecuencias]
        self.longitud_media = (sum(self.longitudes) / len(self.longitudes)) if documentos else 0.0
        df = Counter(t for f in self.frecuencias for t in f)
        n = len(documentos)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    @classmethod
    def desde_almacen(cls, almacen, **parametros) -> "IndiceBM25":
        """Construye el índice con los chunks persistidos; no invoca embeddings."""
        datos = almacen.get(include=["documents", "metadatas"])
        documentos = [Document(id=i, page_content=t, metadata=m or {})
                      for i, t, m in zip(datos["ids"], datos["documents"], datos["metadatas"])]
        return cls(documentos, **parametros)

    def buscar(self, consulta: str, k: int) -> list[ResultadoLexico]:
        """Devuelve como máximo k resultados con puntaje > 0 (puede ser lista vacía)."""
        terminos = set(tokenizar(consulta))
        puntajes = []
        for indice, frecuencia in enumerate(self.frecuencias):
            puntaje = 0.0
            for termino in terminos & frecuencia.keys():
                tf = frecuencia[termino]
                norma = 1 - self.b + self.b * self.longitudes[indice] / (self.longitud_media or 1)
                puntaje += self.idf[termino] * tf * (self.k1 + 1) / (tf + self.k1 * norma)
            if puntaje > 0:
                puntajes.append((puntaje, indice))
        puntajes.sort(key=lambda p: (-p[0], self.documentos[p[1]].id))
        return [ResultadoLexico(self.documentos[i], p) for p, i in puntajes[:k]]
