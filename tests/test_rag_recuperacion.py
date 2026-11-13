"""Bloque 26: recuperación sobre un índice persistido. Embeddings SIMULADOS (sin Gemini)."""
import pytest

from conftest import EmbeddingsSimuladasBolsaPalabras
from src.rag.chunking import dividir_documentos
from src.rag.corpus import MANIFIESTO_BLOQUE24, MANIFIESTO_BLOQUE25, cargar_documentos
from src.rag.errores import EmbeddingsIncompatiblesError, IndiceVacioError
from src.rag.indexador import cargar_indice, indexar
from src.rag.recuperador import buscar, buscar_con_score, crear_retriever


@pytest.fixture
def almacen25(config_temporal):
    config = config_temporal.con(chunk_size=150, chunk_overlap=20)
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE25), "recursivo", 150, 20)
    indexar(chunks, config, EmbeddingsSimuladasBolsaPalabras())
    consulta = EmbeddingsSimuladasBolsaPalabras()
    return cargar_indice(config, consulta), consulta


@pytest.mark.parametrize("k", [1, 2, 3, 5])
def test_k_configurable(almacen25, k):
    almacen, _ = almacen25
    assert len(buscar(almacen, "devoluciones de productos", k=k)) == k
    assert len(crear_retriever(almacen, k=k).invoke("devoluciones de productos")) == k


def test_recupera_el_fragmento_pertinente(almacen25):
    almacen, _ = almacen25
    assert buscar(almacen, "¿Cuántos días hábiles tarda el reembolso?", k=1)[0].metadata["fuente"].endswith("03_reembolso.txt")
    assert buscar(almacen, "cancelarse durante las primeras horas", k=1)[0].metadata["fuente"].endswith("01_cancelacion.txt")


def test_la_recuperacion_cambia_con_la_pregunta(almacen25):
    almacen, _ = almacen25
    a = [d.metadata["fuente"] for d in buscar(almacen, "productos comprados en oferta", k=1)]
    b = [d.metadata["fuente"] for d in buscar(almacen, "costo de envío de la devolución", k=1)]
    assert a != b


def test_scores_son_distancias_ordenadas_no_porcentajes(almacen25):
    almacen, _ = almacen25
    resultados = buscar_con_score(almacen, "reembolso días hábiles", k=5)
    distancias = [s for _, s in resultados]
    assert distancias == sorted(distancias)          # menor distancia = más parecido
    assert all(0.0 <= s <= 2.0 for s in distancias)  # rango de la distancia coseno


def test_consulta_no_reindexa(almacen25):
    almacen, consulta = almacen25
    buscar(almacen, "cancelación", k=2)
    buscar_con_score(almacen, "cancelación", k=2)
    crear_retriever(almacen, 2).invoke("cancelación")
    assert consulta.llamadas_documentos == 0
    assert consulta.llamadas_consulta == 3


def test_indice_vacio_se_detecta_antes_de_consultar(config_temporal):
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "recursivo", 200, 30)
    indexar(chunks[:2], config_temporal, EmbeddingsSimuladasBolsaPalabras(), reconstruir=False)
    almacen = cargar_indice(config_temporal, EmbeddingsSimuladasBolsaPalabras())
    almacen.delete(ids=[c.id for c in chunks[:2]])
    with pytest.raises(IndiceVacioError):
        buscar(almacen, "reintentos", k=3)
    with pytest.raises(IndiceVacioError):
        crear_retriever(almacen, 3)


@pytest.mark.parametrize("pregunta, k", [("", 3), ("   ", 3), ("ok", 0), ("ok", -1), ("ok", True), ("ok", 2.5)])
def test_parametros_invalidos(almacen25, pregunta, k):
    almacen, _ = almacen25
    with pytest.raises(ValueError):
        buscar(almacen, pregunta, k=k)


def test_embeddings_de_dimension_incompatible(config_temporal):
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "recursivo", 200, 30)
    indexar(chunks[:5], config_temporal, EmbeddingsSimuladasBolsaPalabras(dimension=64))
    almacen = cargar_indice(config_temporal, EmbeddingsSimuladasBolsaPalabras(dimension=32))
    with pytest.raises(EmbeddingsIncompatiblesError, match="dimensi"):
        buscar(almacen, "reintentos", k=1)
