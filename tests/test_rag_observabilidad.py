"""Bloque 28: consulta instrumentada, JSONL, estadísticas y preflight.

Sin Gemini: embeddings SIMULADOS, modelos falsos y directorios tmp_path. El índice real no se toca.
"""

import pytest
from langchain_core.messages import AIMessage

from conftest import EmbeddingsSimuladasBolsaPalabras
from src.leer_registros_rag import escribir_informe
from src.rag.chunking import dividir_documentos
from src.rag.configuracion import CONFIG_BLOQUE26_MD
from src.rag.corpus import MANIFIESTO_BLOQUE24, cargar_documentos
from src.rag.costos import Tarifa
from src.rag.errores import ErrorTransitorio
from src.rag.generador import recuperar
from src.rag.indexador import cargar_indice, indexar
from src.rag.observabilidad import (
    ETAPAS, ContextoConsulta, consultar_instrumentado, estadisticas, guardar_registro, leer_registros, relanzar,
)
from src.rag.preflight import ADVERTENCIA, ERROR, OK, comprobar_gitignore, comprobar_indice, comprobar_tarifas
from src.rag.recuperador import buscar_con_score, buscar_por_vector_con_score

TARIFAS = {"gemini-prueba": Tarifa("gemini-prueba", 0.30, 2.50, "https://ejemplo", "2026-11-16", "verificada"),
           "models/simulado": Tarifa("models/simulado", 0.15, None, "https://ejemplo", "2026-11-16", "verificada")}
CTX = ContextoConsulta("markdown", "coleccion_prueba", "models/simulado", "gemini-prueba", "simulada", "ejec-1")
PREGUNTA = "¿Qué agente o herramienta requiere aprobación humana?"


class ModeloFalso:
    """Devuelve contenido en bloques (como Gemini en el Bloque 22) y usage_metadata."""

    def __init__(self, fallos=0, uso=True):
        self.fallos, self.llamadas, self.uso = fallos, 0, uso

    def invoke(self, prompt):
        self.llamadas += 1
        if self.fallos:
            self.fallos -= 1
            raise ConnectionError("red caída (simulado)")
        uso = {"input_tokens": 850, "output_tokens": 90, "total_tokens": 940,
               "output_token_details": {"reasoning": 40}} if self.uso else None
        return AIMessage(content=[{"type": "text", "text": "Respuesta [1] y [2]."}], usage_metadata=uso)


@pytest.fixture
def almacen(tmp_path):
    config = CONFIG_BLOQUE26_MD.con(directorio=tmp_path / "vs", modelo_embeddings="models/simulado")
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "markdown", 200, 30)
    indexar(chunks, config, EmbeddingsSimuladasBolsaPalabras())
    return cargar_indice(config, EmbeddingsSimuladasBolsaPalabras()), config


@pytest.fixture
def sin_esperas(monkeypatch):
    monkeypatch.setattr("src.cliente.time.sleep", lambda _s: None)


# --- Recuperación: compatibilidad y un solo embedding --------------------------------------

def test_busqueda_por_vector_equivale_a_la_busqueda_por_texto(almacen):
    vs, _ = almacen
    emb = EmbeddingsSimuladasBolsaPalabras()
    anterior = buscar_con_score(vs, PREGUNTA, 8)
    nueva = buscar_por_vector_con_score(vs, emb.embed_query(PREGUNTA), 8)
    assert [(d.id, d.metadata, s) for d, s in anterior] == [(d.id, d.metadata, s) for d, s in nueva]
    with pytest.raises(ValueError):
        buscar_por_vector_con_score(vs, [], 3)


def test_consulta_instrumentada_un_solo_embed_y_mismo_contexto_que_recuperar(almacen):
    vs, _ = almacen
    emb = EmbeddingsSimuladasBolsaPalabras()
    registro = consultar_instrumentado(vs, emb, ModeloFalso(), PREGUNTA, CTX, TARIFAS, k=3)
    assert emb.llamadas_consulta == 1 and emb.llamadas_documentos == 0       # sin doble embedding ni reindexación
    referencia = recuperar(vs, PREGUNTA, 3, "vectorial", True)
    assert registro["fuentes"] == sorted({r.documento.metadata["fuente"] for r in referencia})
    assert registro["recuperacion"]["unidades_contexto"] == len(referencia)
    assert registro["estado"] == "ok" and registro["error"] is None


def test_registro_completo_con_tiempos_tokens_y_costos(almacen):
    vs, _ = almacen
    registro = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(), PREGUNTA, CTX, TARIFAS)
    assert set(registro["tiempos_ms"]) == set(ETAPAS)
    assert all(v is not None and v >= 0 for v in registro["tiempos_ms"].values())
    assert registro["tiempo_total_ms"] >= sum(registro["tiempos_ms"].values()) - 1e-6
    assert registro["tokens"]["generacion"] == {"estado": "reportado", "entrada": 850, "salida": 90, "total": 940,
                                                "razonamiento": 40, "cache_lectura": None, "otros": 0}
    assert registro["tokens"]["embedding_consulta"] == {"tokens": None, "estado": "no_reportado_por_el_proveedor"}
    assert registro["costo_usd"]["total_conocido_usd"] == pytest.approx(850 * 0.30 / 1e6 + 90 * 2.50 / 1e6)
    assert registro["respuesta"] == {"caracteres": 20, "intentos": 1, "citas_usadas": [1, 2]}  # contenido en bloques
    assert registro["tipo_medicion"] == "simulada" and registro["tarifas"]["fecha_consulta"] == "2026-11-16"
    assert registro["recuperacion"]["secciones_unicas"] >= 1 and registro["caracteres_contexto"] > 0


def test_tokens_no_disponibles_quedan_en_none(almacen):
    vs, _ = almacen
    registro = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(uso=False), PREGUNTA, CTX, TARIFAS)
    assert registro["tokens"]["generacion"]["estado"] == "no_disponible"
    assert registro["costo_usd"]["total_conocido_usd"] is None


def test_k_mayor_puede_no_aumentar_el_contexto(almacen):
    vs, _ = almacen
    r3 = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(), PREGUNTA, CTX, TARIFAS, k=3)
    r6 = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(), PREGUNTA, CTX, TARIFAS, k=6)
    assert r6["recuperacion"]["unidades_contexto"] >= r3["recuperacion"]["unidades_contexto"]
    assert r6["caracteres_contexto"] >= r3["caracteres_contexto"]


# --- Fallos -----------------------------------------------------------------------------

def test_fallo_de_red_en_generacion_se_registra_y_no_se_oculta(almacen, sin_esperas):
    vs, _ = almacen
    modelo = ModeloFalso(fallos=10)
    registro = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), modelo, PREGUNTA, CTX, TARIFAS)
    assert registro["estado"] == "error" and registro["error"]["tipo"] == "ErrorTransitorio"
    assert registro["error"]["etapas_fallidas"] == ["generacion"]
    assert registro["tiempos_ms"]["embed_query"] is not None and registro["tiempos_ms"]["generacion"] is not None
    assert registro["tokens"]["generacion"]["estado"] == "no_disponible"
    assert modelo.llamadas == 4                                                 # reintentos de src/cliente.py
    with pytest.raises(ErrorTransitorio):
        relanzar(registro)


def test_fallo_en_embedding_deja_etapas_posteriores_sin_medir(almacen):
    vs, _ = almacen

    class EmbFalla(EmbeddingsSimuladasBolsaPalabras):
        def embed_query(self, text):
            raise PermissionError("credencial inválida (simulado)")
    registro = consultar_instrumentado(vs, EmbFalla(), ModeloFalso(), PREGUNTA, CTX, TARIFAS)
    assert registro["estado"] == "error" and registro["error"]["etapas_fallidas"] == ["embed_query"]
    assert registro["tiempos_ms"]["busqueda_vectorial"] is None and registro["tiempos_ms"]["generacion"] is None
    assert registro["tiempo_total_ms"] is not None
    with pytest.raises(PermissionError):
        relanzar(registro)


# --- JSONL ------------------------------------------------------------------------------

def test_jsonl_utf8_acumulativo_y_sin_objetos_internos(almacen, tmp_path, monkeypatch):
    vs, _ = almacen
    monkeypatch.setenv("API_KEY", "CLAVE-SECRETA-NO-DEBE-APARECER")
    ruta = tmp_path / "registros.jsonl"
    pregunta = "¿Qué ocurre con la señal «ñandú» 🚀 y la aprobación?"
    for _ in range(2):
        registro = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(), pregunta, CTX, TARIFAS)
        guardar_registro(registro, ruta)
    error = consultar_instrumentado(vs, EmbeddingsSimuladasBolsaPalabras(), ModeloFalso(fallos=0, uso=False), pregunta, CTX, TARIFAS)
    error["_excepcion"] = RuntimeError("no se serializa")
    guardar_registro(error, ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert texto.count("\n") == 3 and "ñandú" in texto and "🚀" in texto
    assert "CLAVE-SECRETA" not in texto and "_excepcion" not in texto
    registros, errores = leer_registros(ruta)
    assert len(registros) == 3 and errores == []
    assert all(r["pregunta"] == pregunta for r in registros)


def test_lectura_informa_lineas_corruptas(tmp_path):
    ruta = tmp_path / "r.jsonl"
    ruta.write_text('{"estado": "ok"}\nesto no es json\n\n[1, 2]\n', encoding="utf-8")
    registros, errores = leer_registros(ruta)
    assert registros == [{"estado": "ok"}]
    assert [e["linea"] for e in errores] == [2, 4]
    assert leer_registros(tmp_path / "no_existe.jsonl") == ([], [])


# --- Estadísticas e informe -------------------------------------------------------------

def registro_sintetico(total, gen, entrada, salida, costo, tipo="real", estado="ok"):
    return {"tipo_medicion": tipo, "estado": estado, "tiempo_total_ms": total, "sobrecarga_ms": 1.0,
            "tiempos_ms": {"embed_query": 100.0, "generacion": gen}, "caracteres_prompt": entrada * 4,
            "tokens": {"generacion": {"estado": "reportado", "entrada": entrada, "salida": salida, "razonamiento": None}},
            "costo_usd": {"total_conocido_usd": costo}, "recuperacion": {"secciones_unicas": 3},
            "fuentes": ["a.md"], "caso": "c", "k": 3, "id_ejecucion": "e"}


def test_estadisticas_media_mediana_extremos_y_filtro():
    registros = [registro_sintetico(1000, 800, 100, 10, 0.001), registro_sintetico(3000, 2500, 300, 30, 0.003),
                 registro_sintetico(2000, 1500, 200, 20, 0.002), registro_sintetico(9999, 1, 1, 1, 1.0, tipo="simulada"),
                 registro_sintetico(None, None, 5, 5, None, estado="error")]
    est = estadisticas(registros)
    assert est["consultas"] == 3 and est["errores"] == 1
    assert est["total_ms"] == {"n": 3, "media": 2000.0, "mediana": 2000.0, "minimo": 1000, "maximo": 3000}
    assert est["etapas_ms"]["generacion"]["media"] == pytest.approx(1600.0)
    assert est["tokens_entrada"]["media"] == 200.0 and est["costo_generacion_usd"]["media"] == pytest.approx(0.002)
    assert est["caracteres_prompt_por_token_entrada"]["media"] == 4.0
    assert estadisticas([])["total_ms"]["media"] is None


def test_informe_solo_con_datos_registrados(tmp_path):
    ruta = tmp_path / "informe.md"
    escribir_informe([registro_sintetico(1000, 800, 100, 10, 0.001)], [{"linea": 7, "error": "x"}], ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert "| e | c | 3 | ok | 1000 |" in texto and "0.00100000" in texto
    assert "no** representan el rendimiento habitual" in texto and "línea 7" in texto


# --- Preflight ---------------------------------------------------------------------------

def test_preflight_gitignore(tmp_path):
    assert comprobar_gitignore(tmp_path)[0].nivel == ERROR
    (tmp_path / ".gitignore").write_text(".env\n.venv/\nvectorstore/\ngit status --short\n", encoding="utf-8")
    resultados = comprobar_gitignore(tmp_path)
    assert [r.nivel for r in resultados if "excluido." in r.mensaje] == [OK, OK, OK]
    assert any(r.nivel == ADVERTENCIA and "comando" in r.mensaje for r in resultados)
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    assert sum(r.nivel == ERROR for r in comprobar_gitignore(tmp_path)) == 2


def test_preflight_indice_temporal(almacen, tmp_path):
    _, config = almacen
    resultados = comprobar_indice(config)
    assert all(r.nivel == OK for r in resultados)
    assert any("Todos los chunks tienen 'fuente'" in r.mensaje for r in resultados)
    faltante = comprobar_indice(config.con(nombre_coleccion="no_existe"))
    assert faltante[0].nivel == ERROR and "no existe" in faltante[0].mensaje
    assert comprobar_indice(config.con(directorio=tmp_path / "nada"))[0].nivel == ERROR
    otro_modelo = comprobar_indice(config.con(modelo_embeddings="models/otro"))
    assert any(r.nivel == ERROR and r.comprobacion == "embeddings" for r in otro_modelo)


def test_preflight_tarifas_sin_modelo():
    resultados = comprobar_tarifas("modelo-sin-tarifa")
    assert resultados[0].nivel == ADVERTENCIA and "desconocido" in resultados[0].mensaje


def test_preflight_no_modifica_el_indice(almacen):
    _, config = almacen
    antes = cargar_indice(config, EmbeddingsSimuladasBolsaPalabras())._collection.count()
    comprobar_indice(config)
    assert cargar_indice(config, EmbeddingsSimuladasBolsaPalabras())._collection.count() == antes
