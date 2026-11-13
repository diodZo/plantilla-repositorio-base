"""Optimización del Bloque 26: BM25, RRF, chunking por secciones, expansión y evaluación.

Sin Gemini: embeddings SIMULADOS (`EmbeddingsSimuladasBolsaPalabras`) y directorios tmp_path.
"""
import pytest
from langchain_core.documents import Document

from conftest import EmbeddingsSimuladasBolsaPalabras, doc
from src.rag.chunking import comparar_estrategias, dividir_documentos, secciones_markdown
from src.rag.corpus import MANIFIESTO_BLOQUE24, cargar_documentos
from src.rag.evaluacion import (
    ConsultaEvaluacion, cargar_consultas, hit_at_k, primer_acierto, resumir, ResultadoConsulta,
)
from src.rag.expansion import _unir_sin_solapamiento, expandir_documento, expandir_resultados
from src.rag.generador import RESPUESTA_SIN_CONTEXTO, recuperar, responder
from src.rag.hibrido import buscar_hibrido, fusionar_rrf
from src.rag.indexador import cargar_indice, indexar
from src.rag.lexico import IndiceBM25, tokenizar
from src.rag.recuperador import buscar_con_score, formatear_contexto


def d(id_, fuente="docs/a.md", texto=None, **meta):
    return Document(id=id_, page_content=texto or f"texto {id_}", metadata={"fuente": fuente, **meta})


# --- RRF ------------------------------------------------------------------------------

def test_rrf_suma_inversos_de_rango_y_prioriza_consenso():
    vect = [(d("a"), 0.1), (d("b"), 0.2), (d("c"), 0.3)]
    lex = [(d("c"), 9.0), (d("x"), 5.0)]
    resultado = fusionar_rrf(vect, lex, k=4, k_rrf=60)
    assert [r.documento.id for r in resultado] == ["c", "a", "b", "x"]
    c = resultado[0]
    assert c.puntaje_rrf == pytest.approx(1 / 63 + 1 / 61)
    assert (c.rango_vectorial, c.distancia, c.rango_lexico, c.puntaje_bm25) == (3, 0.3, 1, 9.0)


def test_rrf_deduplica_por_id_y_conserva_metadatos():
    vect = [(d("a", "docs/a.md", seccion="S"), 0.1), (d("a", "docs/a.md", seccion="S"), 0.1), (d("b", "docs/b.md"), 0.2)]
    lex = [(d("a", "docs/a.md", seccion="S"), 3.0), (d("b", "docs/b.md"), 2.0)]
    resultado = fusionar_rrf(vect, lex, k=10)
    assert [r.documento.id for r in resultado] == ["a", "b"]
    assert resultado[0].documento.metadata == {"fuente": "docs/a.md", "seccion": "S"}
    assert resultado[1].rango_vectorial == 2  # el duplicado no consumió un rango


def test_rrf_valida_entradas_y_admite_listas_vacias():
    assert fusionar_rrf([], [], k=3) == []
    assert [r.documento.id for r in fusionar_rrf([(d("a"), 0.1)], [], k=3)] == ["a"]
    with pytest.raises(ValueError):
        fusionar_rrf([(Document(page_content="sin id", metadata={}), 0.1)], [], k=1)
    with pytest.raises(ValueError):
        fusionar_rrf([], [], k=0)


# --- BM25 -----------------------------------------------------------------------------

def test_tokenizacion_normaliza_tildes_guiones_bajos_y_raices():
    assert tokenizar("Autorización de la APROBACIÓN") == ["autor", "aprob"]
    assert tokenizar("reembolso_simulado_con_aprobacion") == ["reemb", "simul", "aprob"]
    assert tokenizar("autorice") == tokenizar("autorizar")


def test_bm25_ordena_por_relevancia_y_puede_devolver_vacio():
    indice = IndiceBM25([d("1", texto="reintentos con backoff exponencial"),
                         d("2", texto="costo referencial por tokens"),
                         d("3", texto="backoff backoff y jitter en reintentos")])
    assert [r.documento.id for r in indice.buscar("backoff exponencial", 3)][0] == "1"
    assert indice.buscar("pisco sour", 5) == []
    with pytest.raises(ValueError):
        IndiceBM25([Document(page_content="sin id")])


# --- Chunking por secciones -----------------------------------------------------------

def test_secciones_markdown_respeta_jerarquia_y_bloques_de_codigo():
    texto = "# Título\nIntro.\n## Uso\n```bash\n# comentario, no encabezado\n```\n### Detalle\nTexto.\n## Otra\nMás."
    secciones = secciones_markdown(texto)
    assert [s[0] for s in secciones] == ["Título", "Título > Uso", "Título > Uso > Detalle", "Título > Otra"]
    assert "# comentario, no encabezado" in secciones[1][1]


def test_chunking_markdown_sin_encabezados_aislados_ni_puntos_iniciales():
    documentos = cargar_documentos(MANIFIESTO_BLOQUE24)
    chunks = dividir_documentos(documentos, "markdown", 200, 30)
    assert all(not c.page_content.startswith(". ") for c in chunks)
    assert all(len(c.page_content) >= 40 for c in chunks)
    assert all(c.metadata["fuente"] and "inicio_cuerpo" in c.metadata for c in chunks)
    clave = next(c for c in chunks if "decisión humana explícita" in c.page_content)
    assert clave.page_content.startswith("[Límites de autonomía")
    assert clave.metadata["seccion"].endswith("Supervisión humana")
    assert [c.id for c in chunks] == [c.id for c in dividir_documentos(documentos, "markdown", 200, 30)]
    comparacion = comparar_estrategias(documentos, 200, 30, estrategias=("recursivo", "markdown"))
    assert comparacion["markdown"]["solo_encabezado"] == 0 < comparacion["recursivo"]["solo_encabezado"]
    assert comparacion["markdown"]["empiezan_con_punto"] == 0 < comparacion["recursivo"]["empiezan_con_punto"]
    assert comparacion["markdown"]["cortes_a_mitad_de_palabra"] == 0


# --- Índices temporales ---------------------------------------------------------------

@pytest.fixture
def almacen_md(config_temporal):
    config = config_temporal.con(estrategia="markdown")
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "markdown", 200, 30)
    indexar(chunks, config, EmbeddingsSimuladasBolsaPalabras())
    consulta = EmbeddingsSimuladasBolsaPalabras()
    return cargar_indice(config, consulta), consulta


def test_buscar_hibrido_no_reindexa_y_conserva_fuentes(almacen_md):
    almacen, consulta = almacen_md
    resultados = buscar_hibrido(almacen, "reintentos con backoff exponencial", k=5, candidatos_vectoriales=10,
                                candidatos_lexicos=10)
    assert len(resultados) == 5 and len({r.documento.id for r in resultados}) == 5
    assert all(r.documento.metadata["fuente"] for r in resultados)
    assert consulta.llamadas_documentos == 0 and consulta.llamadas_consulta == 1
    with pytest.raises(ValueError):
        buscar_hibrido(almacen, "x", k=3, candidatos_lexicos=0)


def test_recupera_informacion_de_supervision_humana(almacen_md):
    """Offline: con secciones + expansión, la evidencia entra en el top-3 en modo híbrido.

    Solo se prueba el modo híbrido: su parte léxica es el BM25 real, mientras que los
    embeddings simulados no son semánticos y no representan al modo vectorial real
    (este se mide con Gemini en `python -m src.evaluar_recuperacion`).
    """
    almacen, _ = almacen_md
    pregunta = "¿Qué agente o herramienta requiere aprobación humana?"
    for modo in ("hibrido",):
        documentos = [r.documento for r in recuperar(almacen, pregunta, k=3, modo=modo, expandir=True)]
        assert any("decisión humana explícita" in x.page_content or "aprobador inyectable" in x.page_content
                   for x in documentos), modo
        contexto, citas = formatear_contexto(documentos)
        assert contexto.startswith("[1] ") and set(citas) == {1, 2, 3}
        assert all(f.startswith("docs/") or f == "README.md" for f in citas.values())


def test_expansion_une_la_seccion_y_deduplica(almacen_md):
    almacen, _ = almacen_md
    datos = almacen.get(where={"documento_id": "docs-limites-autonomia-agente-md"})
    chunks = sorted((Document(id=i, page_content=t, metadata=m) for i, t, m in
                     zip(datos["ids"], datos["documents"], datos["metadatas"])), key=lambda c: c.metadata["chunk_index"])
    supervision = [c for c in chunks if c.metadata["seccion"].endswith("Supervisión humana")]
    assert len(supervision) > 1
    expandido = expandir_documento(almacen, supervision[0])
    assert expandido.metadata["expansion"] == "seccion"
    assert "decisión humana explícita" in expandido.page_content
    assert expandido.metadata["fuente"] == "docs/limites_autonomia_agente.md"
    assert expandido.metadata["chunk_ids_expandidos"] == [c.id for c in supervision]
    assert len(expandir_resultados(almacen, supervision)) == 1  # misma sección = una unidad


def test_expansion_con_ventana_si_no_hay_seccion(config_temporal):
    chunks = dividir_documentos(cargar_documentos(MANIFIESTO_BLOQUE24), "recursivo", 200, 30)
    indexar(chunks, config_temporal, EmbeddingsSimuladasBolsaPalabras())
    almacen = cargar_indice(config_temporal, EmbeddingsSimuladasBolsaPalabras())
    objetivo = next(c for c in chunks if "decisión humana explícita" in c.page_content)
    expandido = expandir_documento(almacen, objetivo, ventana=1)
    assert expandido.metadata["expansion"] == "ventana"
    assert len(expandido.metadata["chunk_ids_expandidos"]) == 3
    assert "Las dos herramientas de orientación" in expandido.page_content


def test_expansion_no_inventa_origen_si_falta_metadata(almacen_md):
    almacen, _ = almacen_md
    sin_meta = Document(id="x", page_content="sin origen", metadata={})
    assert expandir_documento(almacen, sin_meta) is sin_meta


def test_union_sin_solapamiento():
    assert _unir_sin_solapamiento(["Hola mundo, esto es", "mundo, esto es una prueba"]) == "Hola mundo, esto es una prueba"
    assert _unir_sin_solapamiento(["Uno.", "Dos."]) == "Uno.\nDos."


# --- Compatibilidad y consultas sin resultados ----------------------------------------

def test_recuperar_por_defecto_equivale_al_recuperador_anterior(almacen_md):
    almacen, _ = almacen_md
    anterior = buscar_con_score(almacen, "costo referencial por tokens", 3)
    nuevo = recuperar(almacen, "costo referencial por tokens", 3)
    assert [x.id for x, _ in anterior] == [r.documento.id for r in nuevo]
    assert [s for _, s in anterior] == [r.puntaje for r in nuevo]
    assert {r.tipo_puntaje for r in nuevo} == {"distancia_coseno"}
    with pytest.raises(ValueError):
        recuperar(almacen, "x", modo="otro")


def test_hibrido_sin_resultados_no_invoca_el_modelo(almacen_md, monkeypatch):
    almacen, _ = almacen_md
    monkeypatch.setattr("src.rag.generador.buscar_hibrido", lambda *_a, **_k: [])

    class ModeloQueNoDebeUsarse:
        def invoke(self, _):
            raise AssertionError("No debía invocarse el modelo")
    respuesta = responder(almacen, ModeloQueNoDebeUsarse(), "¿algo?", modo="hibrido", expandir=True)
    assert respuesta.respuesta == RESPUESTA_SIN_CONTEXTO and respuesta.citas == {}
    assert not respuesta.modelo_invocado and respuesta.metodo == "hibrido"


def test_hibrido_con_lexico_vacio_usa_solo_vectorial(almacen_md):
    almacen, _ = almacen_md
    resultados = buscar_hibrido(almacen, "zzzz qqqq", k=2)
    assert len(resultados) == 2 and all(r.rango_lexico is None for r in resultados)


# --- Evaluación -----------------------------------------------------------------------

def test_hit_at_k_estricto_y_por_fuente():
    consulta = ConsultaEvaluacion("q", "t", "¿?", ("docs/a.md",), ("decisión humana",))
    ranking = [doc("otro", "docs/b.md"), doc("sin evidencia", "docs/a.md"), doc("Una DECISION humana", "docs/a.md")]
    assert primer_acierto(ranking, consulta, estricto=False) == 2
    assert primer_acierto(ranking, consulta, estricto=True) == 3
    assert hit_at_k(ranking, consulta, 3) is True and hit_at_k(ranking, consulta, 2) is False
    fuera = ConsultaEvaluacion("f", "t", "¿?", (), ())
    assert hit_at_k(ranking, fuera, 3) is None
    resultado = ResultadoConsulta(consulta, {m: ranking for m in ("vectorial", "lexico", "hibrido")})
    resumen = resumir([resultado, ResultadoConsulta(fuera, {m: [] for m in ("vectorial", "lexico", "hibrido")})])
    assert resumen["consultas_con_fuente"] == 1
    assert resumen["metodos"]["hibrido"]["hit@3_evidencia"] == 1.0
    assert resumen["metodos"]["hibrido"]["hit@3_fuente"] == 1.0


def test_conjunto_de_evaluacion_cubre_los_temas_pedidos():
    consultas = cargar_consultas()
    temas = {c.tema for c in consultas}
    assert {"reintentos", "costos", "supervision", "fuera_del_corpus"} <= temas
    for c in consultas:
        assert bool(c.fuentes) == bool(c.evidencia)
