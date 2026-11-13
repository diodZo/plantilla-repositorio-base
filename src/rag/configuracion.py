"""Configuración del RAG: rutas absolutas, parámetros de índice y credenciales."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

from src.rag.errores import CredencialesFaltantesError

RAIZ_REPO = Path(__file__).resolve().parents[2]
ARCHIVO_ENV = RAIZ_REPO / ".env"

MODELO_EMBEDDINGS = "models/gemini-embedding-001"
MODELO_CHAT_POR_DEFECTO = "gemini-3.5-flash-lite"
VARIABLES_CLAVE = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "API_KEY")

ESTRATEGIAS = ("recursivo", "fijo", "markdown")
K_POR_DEFECTO = 3


@dataclass(frozen=True)
class ConfiguracionIndice:
    """Todo lo que define un índice persistido. Se guarda en la metadata de la colección."""

    nombre_coleccion: str
    directorio: Path
    chunk_size: int
    chunk_overlap: int
    estrategia: str = "recursivo"
    modelo_embeddings: str = MODELO_EMBEDDINGS

    def __post_init__(self) -> None:
        if self.estrategia not in ESTRATEGIAS:
            raise ValueError(f"Estrategia desconocida: {self.estrategia!r}. Usa {ESTRATEGIAS}.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size debe ser mayor que cero.")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap debe estar entre 0 y chunk_size - 1.")
        if not Path(self.directorio).is_absolute():
            raise ValueError("El directorio del índice debe ser una ruta absoluta.")

    def con(self, **cambios) -> "ConfiguracionIndice":
        return replace(self, **cambios)

    def metadata_coleccion(self) -> dict:
        return {
            "modelo_embeddings": self.modelo_embeddings,
            "estrategia": self.estrategia,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "hnsw:space": "cosine",
        }


CONFIG_BLOQUE24 = ConfiguracionIndice(
    nombre_coleccion="corpus_proyecto_bloque24",
    directorio=RAIZ_REPO / "vectorstore",
    chunk_size=200,
    chunk_overlap=30,
)

# Bloque 26 (optimización): mismo corpus y tamaños que el Bloque 24, chunking por secciones
# Markdown con ruta de encabezados. Colección distinta: el índice del Bloque 24 se conserva.
CONFIG_BLOQUE26_MD = CONFIG_BLOQUE24.con(nombre_coleccion="corpus_proyecto_bloque24_md", estrategia="markdown")

CONFIG_BLOQUE25 = ConfiguracionIndice(
    nombre_coleccion="politicas_tienda_bloque25",
    directorio=RAIZ_REPO / "vectorstore_ejemplo",
    chunk_size=150,
    chunk_overlap=20,
)


def obtener_clave_api(archivo_env: Path | None = ARCHIVO_ENV) -> str:
    """Devuelve la clave de Gemini sin imprimirla.

    Prioridad: GOOGLE_API_KEY, GEMINI_API_KEY, API_KEY (convención de los Bloques 19–23).
    """
    if archivo_env is not None:
        load_dotenv(archivo_env)
    for variable in VARIABLES_CLAVE:
        valor = (os.getenv(variable) or "").strip()
        if valor and valor != "coloca_aqui_tu_clave_real":
            return valor
    raise CredencialesFaltantesError(
        "No hay clave de Gemini. Define GOOGLE_API_KEY, GEMINI_API_KEY o API_KEY en .env "
        f"({ARCHIVO_ENV})."
    )


def obtener_modelo_chat() -> str:
    load_dotenv(ARCHIVO_ENV)
    return os.getenv("AI_MODEL") or MODELO_CHAT_POR_DEFECTO
