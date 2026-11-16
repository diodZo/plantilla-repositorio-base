"""Bloque 27: métricas de recuperación, etiquetado y motor de evaluación. Sin Gemini y sin Chroma."""
import copy
import json
import random

import pytest
from langchain_core.documents import Document

from src.evaluar_bloque27 import escribir_informe
from src.rag.chunking import dividir_documentos
from src.rag.corpus import MANIFIESTO_BLOQUE24, cargar_documentos
from src.rag.etiquetado import contiene_pasaje, id_seccion
from src.rag.evaluacion_bloque27 import (
    ARCHIVO_CASOS, INDICES, Configuracion, DatasetInvalidoError, agregar, cargar_dataset, comparar_ejecuciones,
    detectar_abstencion, etiquetar, evaluar_caso, guardar_ejecucion, huella_etiquetas, peores_casos,
    validar_dataset,
)
from src.rag.expansion import expandir_hasta_k
from src.rag.metricas import (
    deduplicar, f1_score, hit_at_k, metricas_en_k, precision_at_k, promedio, recall_at_k, top_k,
)

# --- Fórmulas: ejemplo del curso ---------------------------------------------------------

EJEMPLO_RECUPERADOS = ["doc2", "doc0", "doc4"]
EJEMPLO_RELEVANTES = {"doc0"}


def test_ejemplo_oficial_k3():
    p = precision_at_k(EJEMPLO_RECUPERADOS, EJEMPLO_RELEVANTES)
    r = recall_at_k(EJEMPLO_RECUPERADOS, EJEMPLO_RELEVANTES)
    assert p == pytest.approx(1 / 3)
    assert r == 1.0
    assert f1_score(p, r) == pytest.approx(0.5)


@pytest.mark.parametrize("k, precision, recall, f1, hit", [
    (1, 0.0, 0.0, 0.0, 0.0),          # solo doc2
    (2, 1 / 2, 1.0, 2 / 3, 1.0),      # doc2, doc0
    (3, 1 / 3, 1.0, 0.5, 1.0),        # doc2, doc0, doc4
    (4, 1 / 3, 1.0, 0.5, 1.0),        # solo hay 3 resultados: el denominador es lo devuelto
    (5, 1 / 3, 1.0, 0.5, 1.0),
])
def test_cinco_valores_de_k_del_ejemplo(k, precision, recall, f1, hit):
    m = metricas_en_k(EJEMPLO_RECUPERADOS, EJEMPLO_RELEVANTES, k)
    assert m["precision"] == pytest.approx(precision)
    assert m["recall"] == pytest.approx(recall)
    assert m["f1"] == pytest.approx(f1)
    assert m["hit"] == hit
    assert m["recuperados"] == EJEMPLO_RECUPERADOS[:k]


# --- Casos límite ------------------------------------------------------------------------

def test_sin_resultados_recuperados():
    assert precision_at_k([], {"a"}) == 0.0
    assert recall_at_k([], {"a"}) == 0.0
    assert f1_score(0.0, 0.0) == 0.0
    assert hit_at_k([], {"a"}) == 0.0


def test_sin_relevantes_recall_none_y_no_es_perfecto():
    assert recall_at_k(["a", "b"], set()) is None
    assert hit_at_k(["a"], []) is None
    assert f1_score(0.0, None) is None
    m = metricas_en_k(["a", "b", "c"], set(), 3)
    assert (m["precision"], m["recall"], m["f1"], m["hit"]) == (0.0, None, None, None)


def test_duplicados_no_cuentan_dos_veces():
    assert deduplicar(["a", "a", "b", "a"]) == ["a", "b"]
    assert precision_at_k(["a", "a", "b"], {"a"}) == 0.5
    assert recall_at_k(["a", "a"], {"a", "b"}) == 0.5
    assert top_k(["a", "a", "b", "c"], 2) == ["a", "b"]  # el duplicado no ocupa una posición


def test_validacion_de_entradas():
    with pytest.raises(TypeError):
        precision_at_k("doc0", {"doc0"})
    with pytest.raises(ValueError):
        recall_at_k(["a", ""], {"a"})
    with pytest.raises(ValueError):
        precision_at_k(["a", 3], {"a"})
    with pytest.raises(ValueError):
        top_k(["a"], 0)
    with pytest.raises(ValueError):
        top_k(["a"], True)
    with pytest.raises(ValueError):
        f1_score(1.2, 0.5)


def test_valores_siempre_entre_cero_y_uno_y_deterministas():
    generador = random.Random(27)
    universo = [f"d{i}" for i in range(12)]
    for _ in range(200):
        ranking = generador.choices(universo, k=generador.randint(0, 8))
        relevantes = set(generador.sample(universo, generador.randint(1, 4)))
        for k in (1, 3, 5):
            m = metricas_en_k(ranking, relevantes, k)
            assert m == metricas_en_k(ranking, relevantes, k)
            for nombre in ("precision", "recall", "f1", "hit"):
                assert 0.0 <= m[nombre] <= 1.0


def test_la_precision_no_siempre_baja_al_aumentar_k():
    ranking, relevantes = ["x", "a", "b"], {"a", "b"}
    assert metricas_en_k(ranking, relevantes, 1)["precision"] < metricas_en_k(ranking, relevantes, 3)["precision"]


def test_promedio_ignora_none():
    assert promedio([1.0, None, 0.0, None]) == {"media": 0.5, "n": 2, "excluidos": 2}
    assert promedio([None, None]) == {"media": None, "n": 0, "excluidos": 2}


# --- Etiquetado --------------------------------------------------------------------------

def test_contiene_pasaje_normaliza_y_admite_cortes():
    pasaje = "La simulación de reembolso sí pide una decisión humana explícita"
    assert contiene_pasaje("...la SIMULACION de reembolso   si pide una decision humana...", pasaje)
    assert contiene_pasaje("x " + pasaje[:45], pasaje)            # pasaje partido en el límite del chunk
    assert not contiene_pasaje("x " + pasaje[:30], pasaje)        # menos de 40 caracteres: no basta
    assert contiene_pasaje("respuesta fija", "Respuesta fija")    # pasaje corto: debe estar completo
    with pytest.raises(ValueError):
        contiene_pasaje("x", "   ")


def test_id_de_seccion():
    assert id_seccion({"documento_id": "d", "seccion": "A > B"}) == "d#A > B"
    assert id_seccion({"documento_id": "d"}) is None


def caso(id_, sin_respuesta=False, **extra):
    base = {"id": id_, "tema": "t", "pregunta": f"¿{id_}?", "justificacion": "j", "sin_respuesta": sin_respuesta,
            "pasajes": [] if sin_respuesta else [{"fuente": "a.md", "texto": "texto relevante del documento a"}]}
    return base | extra


def dataset_sin_congelar(n=8):
    return {"congelado": None, "casos": [caso(f"c{i}") for i in range(n - 1)] + [caso("sr", True)]}


def chunks_falsos():
    return [Document(id=f"a:{i}", page_content=t, metadata={"fuente": "a.md", "documento_id": "a",
                                                            "seccion": s, "chunk_index": i})
            for i, (t, s) in enumerate([("intro", "S1"), ("texto relevante del documento a", "S2"), ("otro", "S2")])]


def test_etiquetar_deriva_ids_y_congela():
    datos = etiquetar(dataset_sin_congelar(), {"base": chunks_falsos(), "markdown": chunks_falsos()},
                      {"a.md": "intro\ntexto relevante del documento a\notro"}, "2026-01-01")
    assert datos["congelado"] == "2026-01-01"
    assert datos["casos"][0]["relevantes"]["markdown"] == {"chunks": ["a:1"], "secciones": ["a#S2"]}
    assert datos["casos"][-1]["relevantes"]["base"] == {"chunks": []}
    with pytest.raises(DatasetInvalidoError, match="congelado"):
        etiquetar(datos, {"base": chunks_falsos(), "markdown": chunks_falsos()}, {"a.md": "x"}, "otra")


def test_etiquetar_rechaza_pasajes_inventados():
    with pytest.raises(DatasetInvalidoError, match="no aparece literalmente"):
        etiquetar(dataset_sin_congelar(), {"base": chunks_falsos(), "markdown": chunks_falsos()},
                  {"a.md": "contenido distinto"}, "f")


# --- Validación del dataset real ---------------------------------------------------------

@pytest.fixture(scope="module")
def dataset_real():
    return cargar_dataset(ARCHIVO_CASOS)


def test_dataset_real_congelado_y_bien_formado(dataset_real):
    casos = dataset_real["casos"]
    assert 8 <= len(casos) <= 15 and dataset_real["congelado"]
    assert sum(c["sin_respuesta"] for c in casos) == 2
    temas = " ".join(c["tema"] for c in casos)
    for tema in ("reintentos", "autenticación", "costos", "herramientas", "memoria", "supervisión",
                 "trazas", "indexación", "recuperación semántica", "fuera del corpus"):
        assert tema in temas


def test_etiquetas_reales_coinciden_con_el_chunking_determinista(dataset_real):
    """Recalcula las etiquetas sin Chroma ni API: deben ser idénticas a las congeladas (IDs no inventados)."""
    documentos = cargar_documentos(MANIFIESTO_BLOQUE24)
    chunks = {n: dividir_documentos(documentos, c.estrategia, c.chunk_size, c.chunk_overlap) for n, c in INDICES.items()}
    sin_congelar = copy.deepcopy(dataset_real) | {"congelado": None}
    for c in sin_congelar["casos"]:
        c.pop("relevantes")
    recalculado = etiquetar(sin_congelar, chunks, {d.metadata["fuente"]: d.page_content for d in documentos}, "x")
    assert [c["relevantes"] for c in recalculado["casos"]] == [c["relevantes"] for c in dataset_real["casos"]]


@pytest.mark.parametrize("mutar, mensaje", [
    (lambda d: d["casos"][0].update(pregunta="otra pregunta"), "huella"),
    (lambda d: d["casos"][0]["relevantes"]["base"]["chunks"].append("x:1"), "huella"),
    (lambda d: d.update(congelado=None), "congelado"),
    (lambda d: d["casos"].__setitem__(1, d["casos"][0]), "únicas"),
    (lambda d: d.update(casos=d["casos"][:5]), "entre 8 y 15"),
    (lambda d: d["casos"][0].update(sin_respuesta=True), "sin respuesta"),  # c01 tiene pasajes
])
def test_validacion_detecta_datasets_alterados(dataset_real, mutar, mensaje):
    alterado = copy.deepcopy(dataset_real)
    mutar(alterado)
    with pytest.raises(DatasetInvalidoError, match=mensaje):
        validar_dataset(alterado)


# --- Motor: chunks frente a secciones ----------------------------------------------------

class AlmacenFalso:
    """Imita `Chroma.get(where=..., include=...)` sobre una lista de chunks (sin Chroma)."""

    def __init__(self, chunks):
        self.chunks = chunks

    def get(self, where=None, include=None):
        condiciones = where.get("$and", [where]) if where else []
        filas = [c for c in self.chunks if all(c.metadata.get(k) == v for cond in condiciones for k, v in cond.items())]
        return {"ids": [c.id for c in filas], "documents": [c.page_content for c in filas],
                "metadatas": [c.metadata for c in filas]}


def chunk(doc, i, seccion, texto=None):
    return Document(id=f"{doc}:{i}", page_content=f"[{seccion}]\n{texto or f'{doc} {seccion} parte {i}'}",
                    metadata={"fuente": f"{doc}.md", "documento_id": doc, "seccion": seccion, "chunk_index": i,
                              "inicio_cuerpo": len(seccion) + 3})


@pytest.fixture
def escenario():
    chunks = [chunk("a", 0, "S1"), chunk("a", 1, "S1"), chunk("a", 2, "S2"), chunk("b", 0, "T1"), chunk("b", 1, "T2")]
    almacen = AlmacenFalso(chunks)
    por_id = {c.id: c for c in chunks}
    ranking = [por_id[i] for i in ("a:0", "a:1", "b:1", "a:2", "b:0")]  # dos chunks de S1 arriba
    caso_r = {"id": "c1", "sin_respuesta": False,
              "relevantes": {"markdown": {"chunks": ["a:1"], "secciones": ["a#S1"]}}}
    configs = (Configuracion("md", "markdown", "chunk", "vectorial", False),
               Configuracion("md_exp", "markdown", "seccion", "vectorial", True))
    return almacen, ranking, caso_r, configs


def test_chunks_y_secciones_se_miden_por_separado(escenario):
    almacen, ranking, caso_r, configs = escenario
    r = evaluar_caso(caso_r, {("markdown", "vectorial"): ranking}, {"markdown": almacen}, configs)
    a3 = r["md"]["3"]
    assert a3["recuperados"] == ["a:0", "a:1", "b:1"]
    assert (a3["precision"], a3["recall"], a3["hit"]) == (pytest.approx(1 / 3), 1.0, 1.0)
    b3 = r["md_exp"]["3"]
    assert b3["recuperados"] == ["a#S1", "b#T2", "a#S2"]   # IDs de sección, no de chunk
    assert b3["precision"] == pytest.approx(1 / 3) and b3["recall"] == 1.0
    assert b3["chunks_en_contexto"] == 4                    # S1 aporta 2 chunks, T2 y S2 uno cada una
    assert b3["caracteres_contexto"] > a3["caracteres_contexto"]


def test_secciones_repetidas_se_cuentan_una_vez(escenario):
    almacen, ranking, _, _ = escenario
    unidades = expandir_hasta_k(almacen, ranking, 5)
    secciones = [id_seccion(u.metadata) for _, u in unidades]
    assert secciones == ["a#S1", "b#T2", "a#S2", "b#T1"]    # a:1 (también S1) no genera otra unidad
    assert [p for p, _ in unidades] == [0, 2, 3, 4]
    assert [u for _, u in expandir_hasta_k(almacen, ranking, 3)] == [u for _, u in unidades[:3]]


def test_evaluacion_determinista_con_ranking_fijo(escenario):
    almacen, ranking, caso_r, configs = escenario
    args = (caso_r, {("markdown", "vectorial"): ranking}, {"markdown": almacen}, configs)
    assert evaluar_caso(*args) == evaluar_caso(*args)


def test_agregados_excluyen_casos_sin_respuesta_y_peores_casos(escenario):
    almacen, ranking, caso_r, configs = escenario
    caso_malo = {"id": "c2", "sin_respuesta": False, "relevantes": {"markdown": {"chunks": ["z:9"], "secciones": ["z#Z"]}}}
    caso_sr = {"id": "c3", "sin_respuesta": True, "relevantes": {"markdown": {"chunks": []}}}
    casos = [caso_r, caso_malo, caso_sr]
    por_caso = {c["id"]: evaluar_caso(c, {("markdown", "vectorial"): ranking}, {"markdown": almacen}, configs)
                for c in casos}
    resumen = agregar(por_caso, casos, configs)
    assert resumen["md"]["3"]["recall"] == {"media": 0.5, "n": 2, "excluidos": 0}
    assert resumen["md"]["3"]["casos_sin_respuesta_excluidos"] == 1
    assert por_caso["c3"]["md"]["3"]["recall"] is None
    assert [f["id"] for f in peores_casos(por_caso, casos, "md", 3)] == ["c2", "c1"]


def test_abstencion_detectada():
    assert detectar_abstencion("La documentación proporcionada no contiene información suficiente para responder.")
    assert not detectar_abstencion("Usa PostgreSQL [1].")


# --- Registro de resultados --------------------------------------------------------------

def ejecucion_minima(id_, recall=1.0, recuperados=("a",)):
    metricas = {"precision": {"media": 0.5}, "recall": {"media": recall}, "f1": {"media": 0.6}, "hit": {"media": 1.0},
                "caracteres_contexto": {"media": 100.0}, "chunks_en_contexto": {"media": 3.0},
                "casos_sin_respuesta_excluidos": 1}
    return {
        "id_ejecucion": id_, "fecha_utc": id_,
        "dataset": {"ruta": "data/x.json", "congelado": "f", "huella_etiquetas": "abc123def456", "casos": 2,
                    "con_respuesta": 1, "sin_respuesta": 1},
        "indices": {"markdown": {"coleccion": "col", "modelo_embeddings": "m", "estrategia": "markdown",
                                 "chunk_size": 200, "chunk_overlap": 30, "documentos": 8, "chunks": 261, "secciones": 90}},
        "parametros": {"ks": [3], "candidatos": 20, "max_seccion": 1200},
        "configuraciones": {"md": {"nivel": "chunk"}},
        "llamadas_api": {"embed_query": 2, "embed_documents": 0, "generaciones": 0},
        "agregados": {"md": {"3": metricas}},
        "por_caso": {"c1": {"md": {"3": {"recuperados": list(recuperados), "precision": 0.5, "recall": recall,
                                         "f1": 0.6, "hit": 1.0}}}},
        "sin_respuesta": {"c2": {"distancia_top1": {"base": 0.4, "markdown": 0.41}, "abstencion_generador": None}},
        "distancia_top1_respondibles": {"markdown": {"min": 0.2, "max": 0.3}},
        "peores_casos": {"md": {"3": [{"id": "c1", "recall": recall, "f1": 0.6, "precision": 0.5}]}},
        "limitaciones": ["pequeño"],
    }


def test_historial_acumula_sin_sobrescribir_y_compara(tmp_path):
    ruta = tmp_path / "resultados.json"
    guardar_ejecucion(ejecucion_minima("t1"), ruta)
    historial = guardar_ejecucion(ejecucion_minima("t2"), ruta)
    assert [e["id_ejecucion"] for e in historial["ejecuciones"]] == ["t1", "t2"]
    assert json.loads(ruta.read_text(encoding="utf-8")) == historial
    with pytest.raises(DatasetInvalidoError, match="Ya existe"):
        guardar_ejecucion(ejecucion_minima("t1"), ruta)
    assert comparar_ejecuciones(ejecucion_minima("a"), ejecucion_minima("b"))["identicas"]
    distinta = comparar_ejecuciones(ejecucion_minima("a"), ejecucion_minima("b", recall=0.0, recuperados=("z",)))
    assert distinta["rankings_distintos"] == [{"caso": "c1", "configuracion": "md", "k": "3"}]
    assert {d["metrica"] for d in distinta["promedios_distintos"]} == {"recall"}


def test_informe_markdown_desde_el_historial(tmp_path):
    md = tmp_path / "r.md"
    escribir_informe({"ejecuciones": [ejecucion_minima("t1"), ejecucion_minima("t2")]}, md)
    texto = md.read_text(encoding="utf-8")
    assert "## Historial de ejecuciones" in texto and texto.count("| t") >= 2
    assert "rangos y promedios idénticos" not in texto and "rankings y promedios idénticos" in texto
    assert "| md | chunk | 3 | 0.500 | 1.000 |" in texto
    assert "200/30" in texto and "no medida" in texto


def test_huella_cambia_con_las_etiquetas():
    a = [caso("x") | {"relevantes": {"base": {"chunks": ["1"]}}}]
    b = copy.deepcopy(a)
    b[0]["relevantes"]["base"]["chunks"] = ["2"]
    assert huella_etiquetas(a) != huella_etiquetas(b)
