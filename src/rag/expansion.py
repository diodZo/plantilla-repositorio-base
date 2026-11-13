"""Expansión de contexto "small-to-big": se busca con chunks pequeños y se entrega la sección.

Para cada chunk recuperado se leen de Chroma (con `get` por metadatos, sin embeddings)
los chunks de la misma sección (`documento_id` + `seccion`, metadato de la estrategia
"markdown") y se unen en orden de `chunk_index`, quitando el solapamiento. Si la sección
excede `max_caracteres`, se usa una ventana de vecinos alrededor del chunk recuperado.
Si el chunk no tiene `seccion` (índices "recursivo"/"fijo"), se usa la ventana de vecinos
por `chunk_index` dentro del mismo documento.

Varios chunks de la misma sección producen una sola entrada (una sola cita).
"""
from __future__ import annotations

from langchain_core.documents import Document

MAX_CARACTERES_SECCION = 1200
VENTANA_VECINOS = 2


def _cuerpo(chunk: Document) -> str:
    return chunk.page_content[chunk.metadata.get("inicio_cuerpo", 0):].strip()


def _unir_sin_solapamiento(partes: list[str], minimo: int = 10) -> str:
    texto = ""
    for parte in partes:
        if not texto:
            texto = parte
            continue
        solape = 0
        for n in range(min(len(texto), len(parte)), minimo - 1, -1):
            if texto.endswith(parte[:n]):
                solape = n
                break
        texto += parte[solape:] if solape else ("\n" if not texto.endswith("\n") else "") + parte
    return texto


def _chunks_relacionados(almacen, documento: Document) -> list[Document]:
    metadata = documento.metadata
    if metadata.get("seccion"):
        filtro = {"$and": [{"documento_id": metadata["documento_id"]}, {"seccion": metadata["seccion"]}]}
    else:
        filtro = {"documento_id": metadata["documento_id"]}
    datos = almacen.get(where=filtro, include=["documents", "metadatas"])
    chunks = [Document(id=i, page_content=t, metadata=m)
              for i, t, m in zip(datos["ids"], datos["documents"], datos["metadatas"])]
    return sorted(chunks, key=lambda c: c.metadata["chunk_index"])


def expandir_documento(almacen, documento: Document, max_caracteres: int = MAX_CARACTERES_SECCION,
                       ventana: int = VENTANA_VECINOS) -> Document:
    """Devuelve un Document con el texto de la sección (o ventana) y metadatos de origen intactos."""
    for clave in ("fuente", "documento_id", "chunk_index"):
        if documento.metadata.get(clave) in (None, ""):
            # Sin metadatos de origen no se puede expandir con seguridad: se devuelve tal cual
            # y formatear_contexto informará la falta de 'fuente' si corresponde.
            return documento
    relacionados = _chunks_relacionados(almacen, documento)
    indice = documento.metadata["chunk_index"]
    seleccion = relacionados
    tiene_seccion = bool(documento.metadata.get("seccion"))
    if not tiene_seccion or sum(len(_cuerpo(c)) for c in relacionados) > max_caracteres:
        seleccion = [c for c in relacionados if abs(c.metadata["chunk_index"] - indice) <= ventana]
    if not seleccion:
        return documento
    cuerpo = _unir_sin_solapamiento([_cuerpo(c) for c in seleccion])
    seccion = documento.metadata.get("seccion", "")
    texto = (f"[{seccion}]\n" if seccion else "") + cuerpo
    metadata = {**documento.metadata,
                "chunk_ids_expandidos": [c.id for c in seleccion],
                "chunk_recuperado": documento.id,
                "expansion": "seccion" if tiene_seccion and seleccion is relacionados else "ventana"}
    return Document(id=documento.id, page_content=texto, metadata=metadata)


def clave_unidad(documento: Document) -> tuple:
    metadata = documento.metadata
    if metadata.get("seccion"):
        return (metadata.get("documento_id"), "seccion", metadata["seccion"])
    return (metadata.get("documento_id"), "chunk", documento.id)


def clave_expandido(original: Document, expandido: Document) -> tuple:
    """Clave de deduplicación: la sección si se expandió a sección; si no, los IDs de la ventana."""
    if expandido.metadata.get("expansion") == "seccion":
        return clave_unidad(original)
    return tuple(expandido.metadata.get("chunk_ids_expandidos", [expandido.id]))


def expandir_resultados(almacen, documentos: list[Document], max_caracteres: int = MAX_CARACTERES_SECCION,
                        ventana: int = VENTANA_VECINOS) -> list[Document]:
    """Expande en orden de ranking y deduplica unidades repetidas (misma sección o misma ventana)."""
    vistos: set = set()
    expandidos: list[Document] = []
    for documento in documentos:
        expandido = expandir_documento(almacen, documento, max_caracteres, ventana)
        clave = clave_expandido(documento, expandido)
        if clave in vistos:
            continue
        vistos.add(clave)
        expandidos.append(expandido)
    return expandidos
