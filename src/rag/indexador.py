"""Indexación idempotente en Chroma, carga sin reindexar y verificación de persistencia."""
from __future__ import annotations

import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.rag.chunking import validar_chunks
from src.rag.configuracion import RAIZ_REPO, ConfiguracionIndice
from src.rag.errores import (
    ColeccionInexistenteError,
    ConfiguracionIncompatibleError,
    DependenciaFaltanteError,
    DirectorioNoEscribibleError,
    EmbeddingsIncompatiblesError,
)

TAMANO_LOTE = 20


def _importar_chroma():
    try:
        import chromadb
        from langchain_chroma import Chroma
    except ImportError as error:
        raise DependenciaFaltanteError(
            "Faltan chromadb o langchain-chroma. Ejecuta: python -m pip install -r requirements.txt"
        ) from error
    return chromadb, Chroma


@dataclass
class ResultadoIndexacion:
    coleccion: str
    directorio: str
    chunks_corpus: int
    agregados: int
    ya_existentes: int
    conteo_final: int
    reconstruido: bool = False
    huerfanos: list[str] = field(default_factory=list)
    podados: int = 0


def verificar_directorio_escribible(directorio: Path) -> None:
    try:
        directorio.mkdir(parents=True, exist_ok=True)
        prueba = directorio / f".prueba_escritura_{uuid.uuid4().hex}"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
    except OSError as error:
        raise DirectorioNoEscribibleError(f"No se puede escribir en {directorio}: {error}") from error


def _cliente(directorio: Path):
    chromadb, _ = _importar_chroma()
    return chromadb.PersistentClient(path=str(directorio))


def _nombres_colecciones(cliente) -> list[str]:
    return [c if isinstance(c, str) else c.name for c in cliente.list_collections()]


def validar_metadata_coleccion(metadata: dict | None, config: ConfiguracionIndice) -> None:
    """Comprueba que el índice persistido se creó con el mismo modelo y chunking."""
    metadata = metadata or {}
    modelo = metadata.get("modelo_embeddings")
    if modelo != config.modelo_embeddings:
        raise EmbeddingsIncompatiblesError(
            f"La colección {config.nombre_coleccion} usa embeddings {modelo!r}, "
            f"pero se configuró {config.modelo_embeddings!r}. Reconstruye con --reconstruir."
        )
    for clave in ("estrategia", "chunk_size", "chunk_overlap"):
        if metadata.get(clave) != getattr(config, clave):
            raise ConfiguracionIncompatibleError(
                f"La colección tiene {clave}={metadata.get(clave)!r}, la configuración pide "
                f"{getattr(config, clave)!r}. Usa la misma configuración o --reconstruir."
            )


def indexar(
    chunks: list[Document],
    config: ConfiguracionIndice,
    embeddings: Embeddings,
    reconstruir: bool = False,
    tamano_lote: int = TAMANO_LOTE,
    pausa_entre_lotes: float = 0.0,
    podar_huerfanos: bool = False,
) -> ResultadoIndexacion:
    """Agrega solo los chunks cuyo ID no está en la colección; nunca borra sin una opción explícita.

    `tamano_lote` y `pausa_entre_lotes` permiten respetar la cuota por minuto de embeddings.
    `podar_huerfanos=True` elimina SOLO los IDs de esta colección que ya no existen en el corpus
    (p. ej., chunks antiguos de un documento editado), después de agregar los nuevos.
    """
    if tamano_lote < 1 or pausa_entre_lotes < 0:
        raise ValueError("tamano_lote debe ser >= 1 y pausa_entre_lotes >= 0.")
    validar_chunks(chunks)
    _, Chroma = _importar_chroma()
    directorio = Path(config.directorio)
    verificar_directorio_escribible(directorio)
    cliente = _cliente(directorio)

    if reconstruir and config.nombre_coleccion in _nombres_colecciones(cliente):
        cliente.delete_collection(config.nombre_coleccion)
    elif config.nombre_coleccion in _nombres_colecciones(cliente):
        validar_metadata_coleccion(cliente.get_collection(config.nombre_coleccion).metadata, config)

    almacen = Chroma(
        client=cliente,
        collection_name=config.nombre_coleccion,
        embedding_function=embeddings,
        collection_metadata=config.metadata_coleccion(),
    )
    ids_corpus = [c.id for c in chunks]
    ids_presentes = set(almacen.get(include=[])["ids"])
    nuevos = [c for c in chunks if c.id not in ids_presentes]

    for inicio in range(0, len(nuevos), tamano_lote):
        if inicio and pausa_entre_lotes:
            time.sleep(pausa_entre_lotes)
        lote = nuevos[inicio:inicio + tamano_lote]
        almacen.add_documents(lote, ids=[c.id for c in lote])

    huerfanos = sorted(ids_presentes - set(ids_corpus))
    if podar_huerfanos and huerfanos:
        almacen.delete(ids=huerfanos)
    return ResultadoIndexacion(
        coleccion=config.nombre_coleccion,
        directorio=str(directorio),
        chunks_corpus=len(chunks),
        agregados=len(nuevos),
        ya_existentes=len(chunks) - len(nuevos),
        conteo_final=almacen._collection.count(),
        reconstruido=reconstruir,
        huerfanos=huerfanos,
        podados=len(huerfanos) if podar_huerfanos else 0,
    )


def planificar_indexacion(chunks: list[Document], config: ConfiguracionIndice) -> dict:
    """Qué cambiaría una indexación, sin embeddings ni escritura: nuevos, existentes y huérfanos."""
    validar_chunks(chunks)
    directorio = Path(config.directorio)
    ids_presentes: set[str] = set()
    existe = False
    if directorio.is_dir():
        cliente = _cliente(directorio)
        if config.nombre_coleccion in _nombres_colecciones(cliente):
            coleccion = cliente.get_collection(config.nombre_coleccion)
            validar_metadata_coleccion(coleccion.metadata, config)
            ids_presentes = set(coleccion.get(include=[])["ids"])
            existe = True
    ids_corpus = [c.id for c in chunks]
    nuevos = [c for c in chunks if c.id not in ids_presentes]
    huerfanos = sorted(ids_presentes - set(ids_corpus))
    return {
        "coleccion_existe": existe,
        "chunks_corpus": len(chunks),
        "nuevos": [c.id for c in nuevos],
        "fuentes_con_nuevos": sorted({c.metadata["fuente"] for c in nuevos}),
        "ya_existentes": len(chunks) - len(nuevos),
        "huerfanos": huerfanos,
    }


def cargar_indice(config: ConfiguracionIndice, embeddings: Embeddings):
    """Abre un índice existente sin crearlo ni reindexarlo."""
    _, Chroma = _importar_chroma()
    directorio = Path(config.directorio)
    if not directorio.is_dir():
        raise ColeccionInexistenteError(
            f"No existe el directorio del índice {directorio}. Ejecuta primero la indexación."
        )
    cliente = _cliente(directorio)
    nombres = _nombres_colecciones(cliente)
    if config.nombre_coleccion not in nombres:
        raise ColeccionInexistenteError(
            f"La colección {config.nombre_coleccion!r} no existe en {directorio}. Disponibles: {nombres or 'ninguna'}."
        )
    validar_metadata_coleccion(cliente.get_collection(config.nombre_coleccion).metadata, config)
    return Chroma(
        client=cliente,
        collection_name=config.nombre_coleccion,
        embedding_function=embeddings,
        create_collection_if_not_exists=False,
    )


def contar_chunks(config: ConfiguracionIndice) -> int:
    """Cuenta los chunks persistidos sin usar embeddings ni la API."""
    directorio = Path(config.directorio)
    if not directorio.is_dir():
        raise ColeccionInexistenteError(f"No existe el directorio del índice {directorio}.")
    cliente = _cliente(directorio)
    if config.nombre_coleccion not in _nombres_colecciones(cliente):
        raise ColeccionInexistenteError(f"La colección {config.nombre_coleccion!r} no existe en {directorio}.")
    return cliente.get_collection(config.nombre_coleccion).count()


def verificar_persistencia(config: ConfiguracionIndice, esperado: int | None = None) -> dict:
    """Verifica directorio, archivos en disco y recuento (en el proceso actual)."""
    directorio = Path(config.directorio)
    archivos = [p for p in directorio.rglob("*") if p.is_file()] if directorio.is_dir() else []
    conteo = contar_chunks(config)
    return {
        "directorio_existe": directorio.is_dir(),
        "archivos": len(archivos),
        "bytes": sum(p.stat().st_size for p in archivos),
        "conteo": conteo,
        "esperado": esperado,
        "consistente": esperado is None or conteo == esperado,
    }


def contar_en_otro_proceso(config: ConfiguracionIndice, timeout: float = 120) -> int:
    """Abre el índice desde un proceso Python nuevo (sin embeddings) y devuelve el recuento."""
    codigo = (
        "import sys, chromadb\n"
        "c = chromadb.PersistentClient(path=sys.argv[1])\n"
        "print(c.get_collection(sys.argv[2]).count())\n"
    )
    proceso = subprocess.run(
        [sys.executable, "-c", codigo, str(config.directorio), config.nombre_coleccion],
        capture_output=True, text=True, timeout=timeout, cwd=str(RAIZ_REPO), check=False,
    )
    if proceso.returncode != 0:
        raise ColeccionInexistenteError(
            f"El proceso de verificación falló (código {proceso.returncode}): {proceso.stderr.strip()[-500:]}"
        )
    return int(proceso.stdout.strip().splitlines()[-1])
