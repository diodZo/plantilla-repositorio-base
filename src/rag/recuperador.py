"""Recuperación semántica sobre un índice persistido y formato de contexto con citas.

Interpretación del score: la colección usa distancia coseno (`hnsw:space=cosine`).
`similarity_search_with_score` devuelve esa DISTANCIA: 0 significa vectores idénticos y
valores mayores, menos similitud (rango teórico 0–2). No es un porcentaje ni una probabilidad.
"""
from __future__ import annotations

from langchain_core.documents import Document

from src.rag.configuracion import K_POR_DEFECTO
from src.rag.errores import EmbeddingsIncompatiblesError, IndiceVacioError, MetadataFaltanteError


def _validar_consulta(pregunta: str, k: int) -> None:
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero mayor o igual a 1.")


def verificar_no_vacio(almacen) -> int:
    conteo = almacen._collection.count()
    if conteo == 0:
        raise IndiceVacioError(
            f"La colección {almacen._collection.name!r} está vacía. Ejecuta primero la indexación."
        )
    return conteo


def _consultar(funcion):
    from chromadb.errors import InvalidArgumentError

    try:
        return funcion()
    except InvalidArgumentError as error:
        # Chroma informa la dimensión incompatible con este tipo; se traduce solo ese caso.
        if "dimension" in str(error).lower():
            raise EmbeddingsIncompatiblesError(
                f"La dimensión de los embeddings de consulta no coincide con el índice: {error}"
            ) from error
        raise


def buscar(almacen, pregunta: str, k: int = K_POR_DEFECTO) -> list[Document]:
    """similarity_search(): los k fragmentos más cercanos por significado."""
    _validar_consulta(pregunta, k)
    verificar_no_vacio(almacen)
    return _consultar(lambda: almacen.similarity_search(pregunta, k=k))


def buscar_con_score(almacen, pregunta: str, k: int = K_POR_DEFECTO) -> list[tuple[Document, float]]:
    """similarity_search_with_score(): (documento, distancia coseno), de menor a mayor distancia."""
    _validar_consulta(pregunta, k)
    verificar_no_vacio(almacen)
    return _consultar(lambda: almacen.similarity_search_with_score(pregunta, k=k))


def crear_retriever(almacen, k: int = K_POR_DEFECTO):
    """as_retriever(): interfaz Runnable estándar de LangChain para el mismo índice."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero mayor o igual a 1.")
    verificar_no_vacio(almacen)
    return almacen.as_retriever(search_type="similarity", search_kwargs={"k": k})


def formatear_contexto(documentos: list[Document]) -> tuple[str, dict[int, str]]:
    """Devuelve el contexto numerado [1], [2], ... y el diccionario {número: fuente}.

    Un documento sin `fuente` no se acepta como fuente válida: se informa con error.
    """
    if not documentos:
        return "", {}
    sin_fuente = [i for i, d in enumerate(documentos, start=1)
                  if not isinstance(d.metadata.get("fuente"), str) or not d.metadata["fuente"].strip()]
    if sin_fuente:
        raise MetadataFaltanteError(
            f"Los documentos recuperados en las posiciones {sin_fuente} no tienen metadata 'fuente'; "
            "no se pueden citar. Reindexa el corpus con metadata de origen."
        )
    bloques = [f"[{i}] {d.page_content.strip()}" for i, d in enumerate(documentos, start=1)]
    citas = {i: d.metadata["fuente"] for i, d in enumerate(documentos, start=1)}
    return "\n\n".join(bloques), citas
