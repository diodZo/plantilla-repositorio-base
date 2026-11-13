"""Dobles de prueba compartidos para el RAG (Bloques 24–26).

SIMULACIÓN: `EmbeddingsSimuladasBolsaPalabras` NO es un modelo semántico real.
Proyecta palabras en un vector mediante hash para que las pruebas sean
deterministas y no consuman cuota de Gemini.
"""
from __future__ import annotations

import hashlib
import math
import re

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.rag.configuracion import ConfiguracionIndice

MODELO_SIMULADO = "simulado/bolsa-de-palabras"


class EmbeddingsSimuladasBolsaPalabras(Embeddings):
    """SIMULACIÓN determinista para pruebas offline. Cuenta llamadas."""

    def __init__(self, dimension: int = 64):
        self.dimension = dimension
        self.llamadas_documentos = 0
        self.llamadas_consulta = 0

    def _vector(self, texto: str) -> list[float]:
        vector = [0.0] * self.dimension
        for palabra in re.findall(r"\w+", texto.lower()):
            if len(palabra) < 3:
                continue
            indice = int(hashlib.md5(palabra.encode()).hexdigest(), 16) % self.dimension
            vector[indice] += 1.0
        norma = math.sqrt(sum(v * v for v in vector)) or 1.0
        if norma == 1.0 and not any(vector):
            vector[0] = 1.0
        return [v / norma for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.llamadas_documentos += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.llamadas_consulta += 1
        return self._vector(text)


@pytest.fixture
def embeddings_simulados():
    return EmbeddingsSimuladasBolsaPalabras()


@pytest.fixture
def config_temporal(tmp_path):
    """Índice en un directorio temporal de pytest; nunca toca vectorstore/ real."""
    return ConfiguracionIndice(
        nombre_coleccion="coleccion_prueba",
        directorio=tmp_path / "indice",
        chunk_size=200,
        chunk_overlap=30,
        modelo_embeddings=MODELO_SIMULADO,
    )


def doc(texto: str, fuente: str, indice: int = 0) -> Document:
    return Document(page_content=texto, metadata={"fuente": fuente, "documento_id": fuente, "chunk_index": indice})
