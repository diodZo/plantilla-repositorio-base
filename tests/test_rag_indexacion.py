"""Bloques 24–25: indexación, persistencia y errores. Embeddings SIMULADOS (sin Gemini)."""
import builtins
import sys
from pathlib import Path

import pytest

from conftest import MODELO_SIMULADO, EmbeddingsSimuladasBolsaPalabras
from src.rag import configuracion, embeddings as modulo_embeddings, indexador
from src.rag.chunking import dividir_documentos
from src.rag.corpus import MANIFIESTO_BLOQUE24, MANIFIESTO_BLOQUE25, cargar_documentos
from src.rag.embeddings import EmbeddingsConReintentos
from src.rag.errores import (
    ColeccionInexistenteError, ConfiguracionIncompatibleError, CredencialesFaltantesError,
    CredencialesInvalidasError, DependenciaFaltanteError, DirectorioNoEscribibleError,
    EmbeddingsIncompatiblesError, ErrorTransitorio,
)
from src.rag.indexador import (
    cargar_indice, contar_chunks, contar_en_otro_proceso, indexar, verificar_persistencia,
)
from src.rag.reintentos import clasificar_error, llamar_con_reintentos


@pytest.fixture(scope="module")
def chunks24():
    return dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "recursivo", 200, 30)


def test_indexa_todos_los_chunks_en_directorio_temporal(chunks24, config_temporal, embeddings_simulados):
    resultado = indexar(chunks24, config_temporal, embeddings_simulados)
    assert resultado.agregados == resultado.conteo_final == len(chunks24)
    assert Path(config_temporal.directorio).is_dir()
    assert config_temporal.directorio.is_relative_to(Path(config_temporal.directorio).parent)


def test_reindexar_no_duplica_ni_recalcula_embeddings(chunks24, config_temporal):
    primeros = EmbeddingsSimuladasBolsaPalabras()
    indexar(chunks24, config_temporal, primeros)
    segundos = EmbeddingsSimuladasBolsaPalabras()
    resultado = indexar(chunks24, config_temporal, segundos)
    assert resultado.agregados == 0 and resultado.ya_existentes == len(chunks24)
    assert resultado.conteo_final == len(chunks24)
    assert segundos.llamadas_documentos == 0


def test_reindexacion_parcial_solo_agrega_nuevos_e_informa_huerfanos(chunks24, config_temporal):
    indexar(chunks24[:-5], config_temporal, EmbeddingsSimuladasBolsaPalabras())
    resultado = indexar(chunks24[5:], config_temporal, EmbeddingsSimuladasBolsaPalabras())
    assert resultado.agregados == 5
    assert resultado.huerfanos == sorted(c.id for c in chunks24[:5])
    assert contar_chunks(config_temporal) == len(chunks24)  # los huérfanos no se borran solos


def test_lotes_y_pausa_respetan_la_cuota(chunks24, config_temporal, monkeypatch):
    pausas = []
    monkeypatch.setattr("src.rag.indexador.time.sleep", pausas.append)
    simulados = EmbeddingsSimuladasBolsaPalabras()
    indexar(chunks24[:25], config_temporal, simulados, tamano_lote=10, pausa_entre_lotes=15)
    assert simulados.llamadas_documentos == 3 and pausas == [15, 15]
    with pytest.raises(ValueError):
        indexar(chunks24[:2], config_temporal, simulados, tamano_lote=0)


def test_reconstruir_solo_con_opcion_explicita(chunks24, config_temporal):
    indexar(chunks24, config_temporal, EmbeddingsSimuladasBolsaPalabras())
    resultado = indexar(chunks24[:10], config_temporal, EmbeddingsSimuladasBolsaPalabras(), reconstruir=True)
    assert resultado.reconstruido and resultado.conteo_final == 10


def test_persistencia_y_recarga_desde_otro_proceso(chunks24, config_temporal):
    indexar(chunks24, config_temporal, EmbeddingsSimuladasBolsaPalabras())
    estado = verificar_persistencia(config_temporal, esperado=len(chunks24))
    assert estado["directorio_existe"] and estado["archivos"] > 0 and estado["bytes"] > 0
    assert estado["consistente"]
    assert contar_en_otro_proceso(config_temporal) == len(chunks24)


def test_cargar_indice_no_reindexa(chunks24, config_temporal):
    indexar(chunks24, config_temporal, EmbeddingsSimuladasBolsaPalabras())
    nuevos = EmbeddingsSimuladasBolsaPalabras()
    almacen = cargar_indice(config_temporal, nuevos)
    assert almacen._collection.count() == len(chunks24)
    assert nuevos.llamadas_documentos == 0


def test_colecciones_aisladas_en_el_mismo_directorio(chunks24, config_temporal):
    chunks25 = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE25), "recursivo", 150, 20)
    config25 = config_temporal.con(nombre_coleccion="politicas_prueba", chunk_size=150, chunk_overlap=20)
    indexar(chunks24, config_temporal, EmbeddingsSimuladasBolsaPalabras())
    indexar(chunks25, config25, EmbeddingsSimuladasBolsaPalabras())
    assert contar_chunks(config_temporal) == len(chunks24)
    assert contar_chunks(config25) == 5
    fuentes = {m["fuente"] for m in cargar_indice(config25, EmbeddingsSimuladasBolsaPalabras()).get()["metadatas"]}
    assert all(f.startswith("data/corpus/tienda/") for f in fuentes)


def test_cargar_coleccion_inexistente_no_la_crea(chunks24, config_temporal):
    with pytest.raises(ColeccionInexistenteError, match="directorio"):
        cargar_indice(config_temporal, EmbeddingsSimuladasBolsaPalabras())
    indexar(chunks24[:3], config_temporal, EmbeddingsSimuladasBolsaPalabras())
    otra = config_temporal.con(nombre_coleccion="no_existe")
    with pytest.raises(ColeccionInexistenteError, match="no_existe"):
        cargar_indice(otra, EmbeddingsSimuladasBolsaPalabras())
    with pytest.raises(ColeccionInexistenteError):
        contar_chunks(otra)


def test_modelo_o_configuracion_incompatibles(chunks24, config_temporal):
    indexar(chunks24[:3], config_temporal, EmbeddingsSimuladasBolsaPalabras())
    with pytest.raises(EmbeddingsIncompatiblesError, match="reconstruir"):
        cargar_indice(config_temporal.con(modelo_embeddings="models/gemini-embedding-001"),
                      EmbeddingsSimuladasBolsaPalabras())
    with pytest.raises(ConfiguracionIncompatibleError, match="chunk_size"):
        indexar(chunks24[:3], config_temporal.con(chunk_size=300), EmbeddingsSimuladasBolsaPalabras())


def test_directorio_sin_permiso_de_escritura(chunks24, config_temporal, monkeypatch):
    def fallar(*_args, **_kwargs):
        raise PermissionError("Acceso denegado (simulado)")
    monkeypatch.setattr(Path, "write_text", fallar)
    with pytest.raises(DirectorioNoEscribibleError, match="Acceso denegado"):
        indexar(chunks24[:3], config_temporal, EmbeddingsSimuladasBolsaPalabras())


def test_dependencia_ausente(monkeypatch):
    importar_original = builtins.__import__

    def importar(nombre, *args, **kwargs):
        if nombre.startswith("langchain_chroma"):
            raise ImportError("simulado")
        return importar_original(nombre, *args, **kwargs)
    monkeypatch.delitem(sys.modules, "langchain_chroma", raising=False)
    monkeypatch.setattr(builtins, "__import__", importar)
    with pytest.raises(DependenciaFaltanteError, match="requirements"):
        indexador._importar_chroma()


def test_credenciales_faltantes_no_se_imprimen(monkeypatch, tmp_path, capsys):
    for variable in configuracion.VARIABLES_CLAVE:
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(CredencialesFaltantesError):
        configuracion.obtener_clave_api(tmp_path / "no_existe.env")
    monkeypatch.setenv("API_KEY", "clave-secreta-de-prueba")
    assert configuracion.obtener_clave_api(None) == "clave-secreta-de-prueba"
    assert "clave-secreta" not in capsys.readouterr().out
    monkeypatch.setenv("API_KEY", "coloca_aqui_tu_clave_real")
    with pytest.raises(CredencialesFaltantesError):
        configuracion.obtener_clave_api(None)


def test_crear_embeddings_gemini_sin_clave_falla_antes_de_llamar(monkeypatch, tmp_path):
    for variable in configuracion.VARIABLES_CLAVE:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(configuracion, "ARCHIVO_ENV", tmp_path / "no_existe.env")
    monkeypatch.setattr(modulo_embeddings, "obtener_clave_api",
                        lambda: configuracion.obtener_clave_api(tmp_path / "no_existe.env"))
    with pytest.raises(CredencialesFaltantesError):
        modulo_embeddings.crear_embeddings_gemini()


# --- Clasificación de errores y reintentos -----------------------------------------

class ErrorApiFalso(Exception):
    def __init__(self, code, mensaje=""):
        super().__init__(f"{code} {mensaje}")
        self.code = code


def envuelto(causa):
    try:
        raise causa
    except Exception as error:
        try:
            raise RuntimeError("Error embedding content") from error
        except RuntimeError as externo:
            return externo


@pytest.mark.parametrize("causa, esperado", [
    (ErrorApiFalso(429, "RESOURCE_EXHAUSTED"), "transitorio"),
    (ErrorApiFalso(503, "UNAVAILABLE"), "transitorio"),
    (ConnectionError("sin red"), "transitorio"),
    (ErrorApiFalso(401), "autenticacion"),
    (ErrorApiFalso(403, "PERMISSION_DENIED"), "autenticacion"),
    (ErrorApiFalso(400, "API key not valid. API_KEY_INVALID"), "autenticacion"),
    (ErrorApiFalso(400, "INVALID_ARGUMENT"), "permanente"),
])
def test_clasificacion_de_errores(causa, esperado):
    assert clasificar_error(envuelto(causa)) == esperado


@pytest.fixture
def sin_esperas(monkeypatch):
    esperas = []
    monkeypatch.setattr("src.cliente.time.sleep", esperas.append)
    return esperas


def test_reintenta_429_con_backoff_y_luego_tiene_exito(sin_esperas):
    respuestas = iter([envuelto(ErrorApiFalso(429)), envuelto(ErrorApiFalso(503)), None])

    def llamada():
        error = next(respuestas)
        if error:
            raise error
        return "ok"
    assert llamar_con_reintentos(llamada, intentos=3, espera_base=1, espera_maxima=10) == "ok"
    assert len(sin_esperas) == 2 and sin_esperas[1] > sin_esperas[0]


def test_agota_reintentos_transitorios(sin_esperas):
    def llamada():
        raise envuelto(ConnectionError("caída"))
    with pytest.raises(ErrorTransitorio):
        llamar_con_reintentos(llamada, intentos=3, espera_base=1)
    assert len(sin_esperas) == 2


def test_no_reintenta_autenticacion(sin_esperas):
    intentos = []

    def llamada():
        intentos.append(1)
        raise envuelto(ErrorApiFalso(400, "API_KEY_INVALID"))
    with pytest.raises(CredencialesInvalidasError):
        llamar_con_reintentos(llamada, intentos=4)
    assert len(intentos) == 1 and sin_esperas == []


def test_errores_de_programacion_se_propagan_sin_reintentar(sin_esperas):
    intentos = []

    def llamada():
        intentos.append(1)
        raise TypeError("bug")
    with pytest.raises(TypeError, match="bug"):
        llamar_con_reintentos(llamada)
    assert len(intentos) == 1


def test_envoltorio_de_embeddings_reintenta_y_cuenta(sin_esperas):
    class Inestable(EmbeddingsSimuladasBolsaPalabras):
        fallos = 1

        def embed_documents(self, texts):
            if self.fallos:
                self.fallos -= 1
                raise envuelto(ErrorApiFalso(429))
            return super().embed_documents(texts)
    envoltorio = EmbeddingsConReintentos(Inestable(), intentos=3, espera_base=1)
    assert len(envoltorio.embed_documents(["a", "b"])) == 2
    assert envoltorio.llamadas_documentos == 1 and envoltorio.textos_embebidos == 2
    assert len(sin_esperas) == 1


def test_modelo_simulado_esta_identificado():
    assert MODELO_SIMULADO.startswith("simulado")
