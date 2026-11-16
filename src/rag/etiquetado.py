"""Etiquetado de relevancia a partir de pasajes literales del documento original (Bloque 27).

Método (independiente del retriever):
1. Para cada pregunta, una persona lee el documento fuente y copia uno o más PASAJES
   literales que la responden.
2. Un chunk es relevante si su cuerpo (sin la ruta de encabezados) contiene al menos
   `MINIMO_FRAGMENTO` caracteres consecutivos de algún pasaje, o el pasaje completo si es
   más corto. La comparación ignora tildes, mayúsculas y espacios repetidos.
3. Los IDs se derivan del chunking determinista (sin API) y se verifican contra Chroma.
4. Una sección es relevante si contiene al menos un chunk relevante.

No se consulta ningún ranking del recuperador para etiquetar.
"""
from __future__ import annotations

import re

from langchain_core.documents import Document

from src.rag.lexico import normalizar

MINIMO_FRAGMENTO = 40


def normalizar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", normalizar(texto)).strip()


def cuerpo_chunk(chunk: Document) -> str:
    return chunk.page_content[chunk.metadata.get("inicio_cuerpo", 0):]


def id_seccion(metadata: dict) -> str | None:
    """Identificador de sección: '<documento_id>#<ruta de encabezados>'. None si no hay sección."""
    seccion = metadata.get("seccion")
    if not seccion or not metadata.get("documento_id"):
        return None
    return f"{metadata['documento_id']}#{seccion}"


def contiene_pasaje(texto: str, pasaje: str, minimo: int = MINIMO_FRAGMENTO) -> bool:
    t, p = normalizar_texto(texto), normalizar_texto(pasaje)
    if not p:
        raise ValueError("El pasaje no puede estar vacío.")
    if len(p) <= minimo:
        return p in t
    return any(p[i:i + minimo] in t for i in range(len(p) - minimo + 1))


def pasaje_existe_en_fuente(texto_fuente: str, pasaje: str) -> bool:
    return normalizar_texto(pasaje) in normalizar_texto(texto_fuente)


def chunks_relevantes(chunks: list[Document], fuente: str, pasajes: list[str]) -> list[str]:
    """IDs (en orden de documento) de los chunks de `fuente` que contienen algún pasaje."""
    return [c.id for c in chunks
            if c.metadata.get("fuente") == fuente and any(contiene_pasaje(cuerpo_chunk(c), p) for p in pasajes)]


def secciones_de(chunks: list[Document], ids: list[str]) -> list[str]:
    por_id = {c.id: c for c in chunks}
    secciones: list[str] = []
    for i in ids:
        s = id_seccion(por_id[i].metadata)
        if s and s not in secciones:
            secciones.append(s)
    return secciones
