"""Bloques 24–25: corpus, chunking, metadata e IDs. Sin llamadas a Gemini."""
import pytest
from langchain_core.documents import Document

from src.rag.chunking import (
    comparar_estrategias, crear_splitter, dividir_documentos, estadisticas_chunks,
    generar_chunk_id, validar_chunks,
)
from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE25, RAIZ_REPO, ConfiguracionIndice
from src.rag.corpus import (
    MANIFIESTO_BLOQUE24, MANIFIESTO_BLOQUE25, FuenteCorpus, cargar_documentos, generar_documento_id,
)
from src.rag.errores import (
    CorpusInvalidoError, DocumentoDuplicadoError, MetadataFaltanteError,
)


@pytest.fixture(scope="module")
def corpus24():
    return cargar_documentos(MANIFIESTO_BLOQUE24)


def test_corpus_real_tiene_cinco_o_mas_documentos_con_origen(corpus24):
    assert len(corpus24) >= 5
    for documento in corpus24:
        assert (RAIZ_REPO / documento.metadata["fuente"]).is_file()
        assert documento.metadata["documento_id"] == generar_documento_id(documento.metadata["fuente"])
        assert documento.page_content.strip()


def test_bloque_solo_se_asigna_cuando_es_fiable(corpus24):
    por_fuente = {d.metadata["fuente"]: d.metadata for d in corpus24}
    assert por_fuente["docs/README-bloque22.md"]["bloque"] == 22
    assert "bloque" not in por_fuente["README.md"]


def test_corpus_rechaza_menos_de_cinco_documentos():
    with pytest.raises(CorpusInvalidoError, match="al menos 5"):
        cargar_documentos(MANIFIESTO_BLOQUE24[:4])


def test_corpus_rechaza_archivo_inexistente_vacio_y_duplicados(tmp_path):
    for i in range(5):
        (tmp_path / f"d{i}.md").write_text(f"contenido {i}", encoding="utf-8")
    fuentes = [FuenteCorpus(f"d{i}.md", None) for i in range(5)]
    assert len(cargar_documentos(fuentes, raiz=tmp_path)) == 5

    with pytest.raises(CorpusInvalidoError, match="No existe"):
        cargar_documentos(fuentes[:4] + [FuenteCorpus("falta.md", None)], raiz=tmp_path)
    (tmp_path / "vacio.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(CorpusInvalidoError, match="vacío"):
        cargar_documentos(fuentes[:4] + [FuenteCorpus("vacio.md", None)], raiz=tmp_path)
    with pytest.raises(DocumentoDuplicadoError, match="dos veces"):
        cargar_documentos(fuentes + [fuentes[0]], raiz=tmp_path)
    (tmp_path / "copia.md").write_text("contenido 0", encoding="utf-8")
    with pytest.raises(DocumentoDuplicadoError, match="mismo contenido"):
        cargar_documentos(fuentes + [FuenteCorpus("copia.md", None)], raiz=tmp_path)


def test_chunking_fijo_respeta_tamano_exacto():
    texto = "".join(f"{i:04d}" for i in range(150))  # 600 caracteres sin repeticiones
    chunks = dividir_documentos([Document(page_content=texto, metadata={"fuente": "x.md", "documento_id": "x"})],
                                "fijo", 200, 30)
    assert [len(c.page_content) for c in chunks][:-1] == [200] * (len(chunks) - 1)
    assert chunks[0].page_content[-30:] == chunks[1].page_content[:30]  # solapamiento


def test_chunking_recursivo_prefiere_limites_naturales():
    texto = ("Primer párrafo con varias palabras de ejemplo.\n\n" * 3) + ("Segunda sección distinta. " * 10)
    documento = Document(page_content=texto, metadata={"fuente": "x.md", "documento_id": "x"})
    for chunk in dividir_documentos([documento], "recursivo", 200, 30):
        assert len(chunk.page_content) <= 200
        assert chunk.page_content[-1] in ".a" or chunk.page_content.endswith("distinta.")


def test_comparacion_real_recursivo_no_corta_palabras(corpus24):
    comparacion = comparar_estrategias(corpus24, 200, 30)
    assert set(comparacion) == {"recursivo", "fijo"}
    assert comparacion["recursivo"]["cortes_a_mitad_de_palabra"] < comparacion["fijo"]["cortes_a_mitad_de_palabra"]
    assert comparacion["fijo"]["maximo"] <= 200 and comparacion["recursivo"]["maximo"] <= 200
    # Varios chunks por documento: cinco documentos no son cinco chunks.
    assert comparacion["recursivo"]["cantidad"] > len(corpus24)


def test_metadata_se_conserva_y_chunk_index_reinicia_por_documento(corpus24):
    chunks = dividir_documentos(corpus24, "recursivo", 200, 30)
    for fuente in {c.metadata["fuente"] for c in chunks}:
        indices = [c.metadata["chunk_index"] for c in chunks if c.metadata["fuente"] == fuente]
        assert indices == list(range(len(indices)))
    bloque22 = [c for c in chunks if c.metadata["fuente"] == "docs/README-bloque22.md"]
    assert all(c.metadata["bloque"] == 22 and c.metadata["documento_id"] == "docs-readme-bloque22-md" for c in bloque22)


def test_ids_son_estables_unicos_y_dependen_del_contenido(corpus24):
    primera = [c.id for c in dividir_documentos(corpus24, "recursivo", 200, 30)]
    segunda = [c.id for c in dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "recursivo", 200, 30)]
    assert primera == segunda
    assert len(set(primera)) == len(primera)
    assert generar_chunk_id("d", 0, "a") != generar_chunk_id("d", 0, "b")
    assert generar_chunk_id("d", 3, "a").startswith("d:0003:")


def test_parametros_configurables_y_validados(corpus24):
    menos = dividir_documentos(corpus24, "recursivo", 400, 50)
    mas = dividir_documentos(corpus24, "recursivo", 200, 30)
    assert len(menos) < len(mas)
    with pytest.raises(ValueError):
        crear_splitter("recursivo", 100, 100)
    with pytest.raises(ValueError):
        crear_splitter("otro", 100, 10)
    with pytest.raises(ValueError):
        ConfiguracionIndice("abc", RAIZ_REPO / "x", 0, 0)
    with pytest.raises(ValueError, match="absoluta"):
        ConfiguracionIndice("abc", "relativa", 100, 10)


def test_configuraciones_por_defecto_de_los_bloques():
    assert (CONFIG_BLOQUE24.chunk_size, CONFIG_BLOQUE24.chunk_overlap) == (200, 30)
    assert (CONFIG_BLOQUE25.chunk_size, CONFIG_BLOQUE25.chunk_overlap) == (150, 20)
    assert CONFIG_BLOQUE24.directorio == RAIZ_REPO / "vectorstore"
    assert CONFIG_BLOQUE25.directorio == RAIZ_REPO / "vectorstore_ejemplo"
    assert CONFIG_BLOQUE24.nombre_coleccion != CONFIG_BLOQUE25.nombre_coleccion
    assert CONFIG_BLOQUE24.modelo_embeddings == "models/gemini-embedding-001"


def test_bloque25_produce_cinco_chunks_sin_vacios_ni_duplicados():
    documentos = cargar_documentos(MANIFIESTO_BLOQUE25)
    chunks = dividir_documentos(documentos, "recursivo", 150, 20)
    assert len(documentos) == 5 and len(chunks) == 5
    assert all(c.page_content.strip() for c in chunks)
    assert len({c.page_content for c in chunks}) == 5
    assert estadisticas_chunks(chunks)["maximo"] <= 150


def test_validar_chunks_detecta_problemas():
    base = {"fuente": "a.md", "documento_id": "a", "chunk_index": 0}
    with pytest.raises(MetadataFaltanteError):
        validar_chunks([Document(id="1", page_content="x", metadata={"fuente": "a.md"})])
    with pytest.raises(DocumentoDuplicadoError):
        validar_chunks([Document(id="1", page_content="x", metadata=base),
                        Document(id="1", page_content="y", metadata=base)])
    with pytest.raises(DocumentoDuplicadoError):
        validar_chunks([Document(id="1", page_content="x", metadata=base),
                        Document(id="2", page_content="x", metadata={**base, "chunk_index": 1})])
    with pytest.raises(ValueError, match="vacío"):
        validar_chunks([Document(id="1", page_content="  ", metadata=base)])
    # Mismo texto en otra fuente: permitido.
    validar_chunks([Document(id="1", page_content="x", metadata=base),
                    Document(id="2", page_content="x", metadata={**base, "documento_id": "b", "fuente": "b.md"})])


def test_documento_sin_metadata_no_se_divide():
    with pytest.raises(MetadataFaltanteError):
        dividir_documentos([Document(page_content="texto")], "recursivo", 200, 30)


def test_estadisticas_vacias():
    assert estadisticas_chunks([])["cantidad"] == 0
