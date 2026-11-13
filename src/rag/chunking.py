"""Chunking fijo, recursivo y por secciones Markdown, con metadata, IDs estables y estadísticas."""
from __future__ import annotations

import hashlib
import re
from statistics import mean

from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

from src.rag.configuracion import ESTRATEGIAS
from src.rag.errores import DocumentoDuplicadoError, MetadataFaltanteError

SEPARADORES_NATURALES = ["\n\n", "\n", ". ", " ", ""]
METADATA_OBLIGATORIA = ("fuente", "documento_id", "chunk_index")


def crear_splitter(estrategia: str, chunk_size: int, chunk_overlap: int):
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero.")
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap debe estar entre 0 y chunk_size - 1.")
    if estrategia == "fijo":
        # separator="" corta por número de caracteres, sin buscar límites naturales.
        return CharacterTextSplitter(separator="", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if estrategia == "recursivo":
        return RecursiveCharacterTextSplitter(
            separators=SEPARADORES_NATURALES, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
    if estrategia == "markdown":
        # keep_separator="end": el ". " queda al final de la frase, no al inicio del chunk siguiente.
        return RecursiveCharacterTextSplitter(
            separators=SEPARADORES_NATURALES, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            keep_separator="end",
        )
    raise ValueError(f"Estrategia desconocida: {estrategia!r}. Usa {ESTRATEGIAS}.")


def generar_chunk_id(documento_id: str, chunk_index: int, texto: str) -> str:
    """Determinista: mismo documento, posición y contenido -> mismo ID."""
    huella = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:10]
    return f"{documento_id}:{chunk_index:04d}:{huella}"


PATRON_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def secciones_markdown(texto: str) -> list[tuple[str, str]]:
    """Divide por encabezados (fuera de bloques de código) y devuelve (ruta de títulos, cuerpo).

    La ruta acumula la jerarquía: "Título > Sección > Subsección". Los encabezados no
    generan chunks propios: pasan a ser contexto de los fragmentos de su sección.
    """
    secciones: list[tuple[str, str]] = []
    ruta: list[tuple[int, str]] = []
    cuerpo: list[str] = []
    en_codigo = False

    def cerrar() -> None:
        texto_cuerpo = "\n".join(cuerpo).strip()
        if texto_cuerpo:
            secciones.append((" > ".join(t for _, t in ruta), texto_cuerpo))
        cuerpo.clear()

    for linea in texto.split("\n"):
        if linea.lstrip().startswith("```"):
            en_codigo = not en_codigo
        coincidencia = None if en_codigo else PATRON_ENCABEZADO.match(linea)
        if coincidencia:
            cerrar()
            nivel = len(coincidencia.group(1))
            while ruta and ruta[-1][0] >= nivel:
                ruta.pop()
            ruta.append((nivel, re.sub(r"[*`]", "", coincidencia.group(2)).strip()))
        else:
            cuerpo.append(linea)
    cerrar()
    return secciones


def _fragmentos(texto: str, estrategia: str, splitter) -> list[tuple[str, dict]]:
    """(texto del chunk, metadata adicional). En "markdown" antepone la ruta de la sección."""
    if estrategia != "markdown":
        return [(t, {}) for t in splitter.split_text(texto) if t.strip()]
    fragmentos = []
    for ruta, cuerpo in secciones_markdown(texto):
        prefijo = f"[{ruta}]\n" if ruta else ""
        for pieza in splitter.split_text(cuerpo):
            if pieza.strip():
                fragmentos.append((prefijo + pieza.strip(), {"seccion": ruta, "inicio_cuerpo": len(prefijo)}))
    return fragmentos


def dividir_documentos(
    documentos: list[Document], estrategia: str, chunk_size: int, chunk_overlap: int
) -> list[Document]:
    """Divide cada documento por separado; `chunk_index` reinicia en 0 por documento."""
    splitter = crear_splitter(estrategia, chunk_size, chunk_overlap)
    chunks: list[Document] = []
    for documento in documentos:
        faltantes = [c for c in ("fuente", "documento_id") if not documento.metadata.get(c)]
        if faltantes:
            raise MetadataFaltanteError(f"Documento sin metadata {faltantes}: {documento.page_content[:60]!r}")
        for indice, (texto, extra) in enumerate(_fragmentos(documento.page_content, estrategia, splitter)):
            metadata = {**documento.metadata, **extra, "chunk_index": indice}
            chunk_id = generar_chunk_id(documento.metadata["documento_id"], indice, texto)
            chunks.append(Document(id=chunk_id, page_content=texto, metadata=metadata))
    validar_chunks(chunks)
    return chunks


def validar_chunks(chunks: list[Document]) -> None:
    """Rechaza chunks vacíos, sin metadata, con ID repetido o con texto repetido dentro de un documento.

    El mismo texto en dos fuentes distintas se permite: son citas de origen diferente.
    """
    ids: set[str] = set()
    textos: dict[tuple[str, str], str] = {}
    for chunk in chunks:
        if not chunk.page_content.strip():
            raise ValueError(f"Chunk vacío: {chunk.id}")
        faltantes = [c for c in METADATA_OBLIGATORIA if chunk.metadata.get(c) in (None, "")]
        if faltantes or not chunk.id:
            raise MetadataFaltanteError(f"Chunk sin {faltantes or ['id']}: {chunk.page_content[:60]!r}")
        if chunk.id in ids:
            raise DocumentoDuplicadoError(f"ID de chunk repetido: {chunk.id}")
        ids.add(chunk.id)
        clave = (chunk.metadata["documento_id"], chunk.page_content.strip())
        if clave in textos:
            raise DocumentoDuplicadoError(f"Texto repetido en {textos[clave]} y {chunk.id}")
        textos[clave] = chunk.id


def estadisticas_chunks(chunks: list[Document]) -> dict:
    longitudes = [len(c.page_content) for c in chunks]
    if not longitudes:
        return {"cantidad": 0, "minimo": 0, "maximo": 0, "promedio": 0.0}
    return {
        "cantidad": len(longitudes),
        "minimo": min(longitudes),
        "maximo": max(longitudes),
        "promedio": round(mean(longitudes), 1),
    }


def comparar_estrategias(
    documentos: list[Document], chunk_size: int, chunk_overlap: int, ejemplos: int = 2,
    estrategias: tuple[str, ...] = ("recursivo", "fijo"),
) -> dict[str, dict]:
    """Estadísticas y ejemplos de las estrategias indicadas, sin llamadas a la API."""
    resultado = {}
    for estrategia in estrategias:
        chunks = dividir_documentos(documentos, estrategia, chunk_size, chunk_overlap)
        resultado[estrategia] = {
            **estadisticas_chunks(chunks),
            "ejemplos": [c.page_content for c in chunks[:ejemplos]],
            "cortes_a_mitad_de_palabra": contar_cortes_de_palabra(documentos, chunks),
            "menores_de_40": sum(len(c.page_content) < 40 for c in chunks),
            "solo_encabezado": sum(c.page_content.lstrip().startswith("#") and "\n" not in c.page_content.strip()
                                   for c in chunks),
            "empiezan_con_punto": sum(c.page_content.startswith(". ") for c in chunks),
        }
    return resultado


def contar_cortes_de_palabra(documentos: list[Document], chunks: list[Document]) -> int:
    """Cuenta chunks cuyo final cae dentro de una palabra del documento original."""
    textos = {d.metadata["documento_id"]: d.page_content for d in documentos}
    cursores: dict[str, int] = {}
    cortes = 0
    for chunk in chunks:
        doc_id = chunk.metadata["documento_id"]
        texto = textos[doc_id]
        cuerpo = chunk.page_content[chunk.metadata.get("inicio_cuerpo", 0):]
        inicio = texto.find(cuerpo, cursores.get(doc_id, 0))
        if inicio < 0:
            continue
        cursores[doc_id] = inicio + 1
        fin = inicio + len(cuerpo)
        if fin < len(texto) and texto[fin - 1].isalnum() and texto[fin].isalnum():
            cortes += 1
    return cortes
