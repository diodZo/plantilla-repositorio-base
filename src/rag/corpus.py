"""Carga de corpus con metadata de origen.

El corpus del Bloque 24 se lee desde los archivos reales del repositorio,
sin copiarlos, para que `fuente` apunte siempre al documento original.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

from src.rag.configuracion import RAIZ_REPO
from src.rag.errores import CorpusInvalidoError, DocumentoDuplicadoError


@dataclass(frozen=True)
class FuenteCorpus:
    ruta: str              # relativa a la raíz del repositorio, con "/"
    bloque: int | None     # solo si el archivo pertenece inequívocamente a un bloque
    tema: str = ""


MANIFIESTO_BLOQUE24: tuple[FuenteCorpus, ...] = (
    FuenteCorpus("README.md", None, "cliente con reintentos, costo referencial y estructura"),
    FuenteCorpus("docs/ensayo-bloque13.md", 13, "backoff, cuota y costos"),
    FuenteCorpus("docs/decision-arquitectura.md", None, "ADR: elección de modelo, costo y latencia"),
    FuenteCorpus("docs/README-bloque20.md", 20, "manejo de errores y fallbacks"),
    FuenteCorpus("docs/README-bloque21.md", 21, "agente con herramientas"),
    FuenteCorpus("docs/README-bloque22.md", 22, "memoria conversacional"),
    FuenteCorpus("docs/README-bloque23.md", 23, "supervisión humana y trazas"),
    FuenteCorpus("docs/limites_autonomia_agente.md", 23, "límites de autonomía"),
)

MANIFIESTO_BLOQUE25: tuple[FuenteCorpus, ...] = tuple(
    FuenteCorpus(f"data/corpus/tienda/{nombre}", 25, tema)
    for nombre, tema in (
        ("01_cancelacion.txt", "cancelación"),
        ("02_devolucion.txt", "devolución"),
        ("03_reembolso.txt", "reembolso"),
        ("04_ofertas.txt", "excepciones en ofertas"),
        ("05_envio_devoluciones.txt", "costo de envío de devoluciones"),
    )
)

MINIMO_DOCUMENTOS = 5


def generar_documento_id(ruta_relativa: str) -> str:
    """ID legible y determinista a partir de la ruta: docs/README-x.md -> docs-readme-x-md."""
    return re.sub(r"[^a-z0-9]+", "-", ruta_relativa.lower()).strip("-")


def cargar_documentos(
    fuentes: tuple[FuenteCorpus, ...] | list[FuenteCorpus],
    raiz: Path = RAIZ_REPO,
    minimo: int = MINIMO_DOCUMENTOS,
) -> list[Document]:
    """Lee cada fuente en UTF-8 y devuelve un Document con su metadata de origen."""
    if len(fuentes) < minimo:
        raise CorpusInvalidoError(f"El corpus necesita al menos {minimo} documentos; hay {len(fuentes)}.")

    documentos: list[Document] = []
    rutas_vistas: set[str] = set()
    contenidos_vistos: dict[str, str] = {}
    for fuente in fuentes:
        ruta_normalizada = Path(fuente.ruta).as_posix()
        if ruta_normalizada in rutas_vistas:
            raise DocumentoDuplicadoError(f"La fuente {ruta_normalizada} aparece dos veces en el manifiesto.")
        rutas_vistas.add(ruta_normalizada)

        ruta = raiz / ruta_normalizada
        if not ruta.is_file():
            raise CorpusInvalidoError(f"No existe el documento del corpus: {ruta}")
        texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not texto.strip():
            raise CorpusInvalidoError(f"El documento está vacío: {ruta_normalizada}")

        huella = hashlib.sha256(texto.strip().encode("utf-8")).hexdigest()
        if huella in contenidos_vistos:
            raise DocumentoDuplicadoError(
                f"{ruta_normalizada} tiene el mismo contenido que {contenidos_vistos[huella]}."
            )
        contenidos_vistos[huella] = ruta_normalizada

        metadata = {"fuente": ruta_normalizada, "documento_id": generar_documento_id(ruta_normalizada)}
        if fuente.bloque is not None:
            metadata["bloque"] = fuente.bloque
        documentos.append(Document(page_content=texto, metadata=metadata))
    return documentos
