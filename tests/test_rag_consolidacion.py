"""Consolidación del RAG: modo predeterminado de la CLI, compatibilidad, límite de contexto,
métricas, actualización incremental y conjuntos de evaluación. Sin Gemini (embeddings SIMULADOS)."""
import json

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from conftest import EmbeddingsSimuladasBolsaPalabras
from src import recuperar_corpus
from src.rag.chunking import dividir_documentos
from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE26_MD
from src.rag.corpus import MANIFIESTO_BLOQUE24, cargar_documentos
from src.rag.evaluacion import ARCHIVO_CONSULTAS, ARCHIVO_VALIDACION, cargar_consultas
from src.rag.generador import (
    ResultadoRecuperado, aplicar_limite_contexto, calcular_metricas, preparar_contexto, recuperar, responder,
)
from src.rag.indexador import cargar_indice, contar_chunks, indexar, planificar_indexacion
from src.rag.prompts import INSTRUCCIONES_SISTEMA, construir_prompt
from src.rag.recuperador import buscar_con_score


def unidad(texto, fuente="docs/a.md", **meta):
    return ResultadoRecuperado(Document(id=texto[:8], page_content=texto, metadata={"fuente": fuente, **meta}),
                               0.1, "distancia_coseno")


# --- CLI: valores predeterminados y opciones --------------------------------------------

def test_cli_por_defecto_markdown_vectorial_con_expansion():
    opciones = recuperar_corpus.construir_parser().parse_args(["¿algo?"])
    assert (opciones.indice, opciones.modo, opciones.expandir, opciones.max_contexto, opciones.k) == \
        ("markdown", "vectorial", True, None, 3)
    assert recuperar_corpus.resolver_configuracion(opciones) == CONFIG_BLOQUE26_MD
    assert CONFIG_BLOQUE26_MD.estrategia == "markdown"


def test_cli_opciones_explicitas_para_modo_anterior_e_hibrido():
    parser = recuperar_corpus.construir_parser()
    anterior = parser.parse_args(["x", "--indice", "base", "--sin-expandir"])
    assert recuperar_corpus.resolver_configuracion(anterior) == CONFIG_BLOQUE24 and anterior.expandir is False
    hibrido = parser.parse_args(["x", "--modo", "hibrido", "--max-contexto", "2500", "--max-seccion", "800"])
    assert (hibrido.modo, hibrido.max_contexto, hibrido.max_seccion) == ("hibrido", 2500, 800)
    assert parser.parse_args(["x", "--expandir"]).expandir is True  # aceptado por compatibilidad
    with pytest.raises(SystemExit):
        parser.parse_args(["x", "--expandir", "--sin-expandir"])
    with pytest.raises(SystemExit):
        parser.parse_args(["x", "--indice", "otro"])


def test_cli_exige_pregunta_o_escenarios():
    with pytest.raises(SystemExit):
        recuperar_corpus.main([])


@pytest.fixture
def indices_temporales(tmp_path, monkeypatch):
    """Índices markdown y base en tmp_path; la CLI los usa en lugar de vectorstore/."""
    documentos = cargar_documentos(MANIFIESTO_BLOQUE24)
    configs = {
        "markdown": CONFIG_BLOQUE26_MD.con(directorio=tmp_path / "vs", modelo_embeddings="simulado/bolsa"),
        "base": CONFIG_BLOQUE24.con(directorio=tmp_path / "vs", modelo_embeddings="simulado/bolsa"),
    }
    for config in configs.values():
        indexar(dividir_documentos(documentos, config.estrategia, 200, 30), config, EmbeddingsSimuladasBolsaPalabras())
    for nombre, config in configs.items():
        monkeypatch.setitem(recuperar_corpus.INDICES, nombre, config)
    monkeypatch.setattr(recuperar_corpus, "crear_embeddings_gemini", lambda *_a: EmbeddingsSimuladasBolsaPalabras())
    return configs


def test_cli_modo_predeterminado_sin_reindexar_y_con_metricas(indices_temporales, capsys):
    # Se observó una falla intermitente (2 de ~41 ejecuciones de la suite completa) sin traza
    # capturada; los mensajes incluyen la salida completa para poder diagnosticarla.
    codigo = recuperar_corpus.main(["¿Qué agente o herramienta requiere aprobación humana?", "--sin-generar"])
    capturado = capsys.readouterr()
    salida = capturado.out
    detalle = f"código={codigo}\nSTDOUT:\n{salida}\nSTDERR:\n{capturado.err}"
    assert codigo == 0, detalle
    assert "corpus_proyecto_bloque24_md con" in salida, detalle
    assert "expandir=True" in salida and "seccion=" in salida, detalle
    assert "Métricas:" in salida and "'secciones_expandidas'" in salida, detalle
    assert "embed_documents=0" in salida, detalle


def test_cli_modo_anterior_y_generacion_con_citas(indices_temporales, capsys, monkeypatch):
    modelo = FakeListChatModel(responses=["La respuesta está en la documentación [1]."])
    monkeypatch.setattr(recuperar_corpus, "crear_modelo_chat", lambda: modelo)
    assert recuperar_corpus.main(["costo referencial por tokens", "--indice", "base", "--sin-expandir"]) == 0
    salida = capsys.readouterr().out
    assert "corpus_proyecto_bloque24 con" in salida and "expandir=False" in salida
    assert "'citas_usadas': [1]" in salida and "'citas_invalidas': []" in salida
    assert "embed_documents=0" in salida


# --- Compatibilidad de la API de biblioteca ---------------------------------------------

@pytest.fixture
def almacen_md(indices_temporales):
    return cargar_indice(indices_temporales["markdown"], EmbeddingsSimuladasBolsaPalabras())


def test_api_conserva_valores_por_defecto_anteriores(almacen_md):
    anterior = buscar_con_score(almacen_md, "reintentos con backoff", 3)
    assert [d.id for d, _ in anterior] == [r.documento.id for r in recuperar(almacen_md, "reintentos con backoff")]
    respuesta = responder(almacen_md, FakeListChatModel(responses=["ok [1]"]), "reintentos con backoff")
    assert respuesta.metodo == "vectorial" and len(respuesta.distancias) == 3
    assert respuesta.metricas["secciones_expandidas"] == 0 and respuesta.metricas["chunks_recuperados"] == 3


def test_expansion_y_limite_conservan_citas(almacen_md):
    incluidos, omitidos, contexto, citas = preparar_contexto(
        almacen_md, "¿Qué agente o herramienta requiere aprobación humana?", k=4, modo="hibrido",
        expandir=True, max_contexto=900)
    assert list(citas) == list(range(1, len(incluidos) + 1))
    assert all(f == r.documento.metadata["fuente"] for f, r in zip(citas.values(), incluidos))
    for numero, resultado in enumerate(incluidos, start=1):
        assert f"[{numero}] {resultado.documento.page_content.strip()}" in contexto  # unidades completas
    assert len(incluidos) + len(omitidos) == 4
    metricas = calcular_metricas(incluidos, omitidos, contexto, citas)
    assert metricas["caracteres_contexto"] == len(contexto)
    assert metricas["secciones_expandidas"] + metricas["ventanas_expandidas"] == len(incluidos)


# --- Límite de contexto y métricas ------------------------------------------------------

def test_limite_incluye_unidades_completas_y_nunca_recorta():
    unidades = [unidad("A" * 100), unidad("B" * 100), unidad("C" * 100)]
    assert aplicar_limite_contexto(unidades, None) == (unidades, [])
    incluidos, omitidos = aplicar_limite_contexto(unidades, 220)  # 104 + 2 + 104 = 210 ≤ 220
    assert incluidos == unidades[:2] and omitidos == unidades[2:]
    assert all(r.documento.page_content in ("A" * 100, "B" * 100) for r in incluidos)


def test_limite_conserva_siempre_la_primera_unidad_y_respeta_el_orden():
    grande, chica = unidad("X" * 500), unidad("y" * 10)
    assert aplicar_limite_contexto([grande, chica], 50) == ([grande], [chica])
    with pytest.raises(ValueError):
        aplicar_limite_contexto([grande], 0)


def test_metricas_detectan_citas_usadas_e_invalidas():
    incluidos = [unidad("uno", expansion="seccion", chunk_ids_expandidos=["a", "b"]),
                 unidad("dos", "docs/b.md")]
    metricas = calcular_metricas(incluidos, [], "ctx", {1: "docs/a.md", 2: "docs/b.md"}, "Hecho [2] y otro [5].")
    assert metricas["chunks_recuperados"] == 3 and metricas["secciones_expandidas"] == 1
    assert metricas["citas_usadas"] == [2, 5] and metricas["fuentes_citadas"] == ["docs/b.md"]
    assert metricas["citas_invalidas"] == [5]


# --- Prompt -----------------------------------------------------------------------------

def test_prompt_pide_redaccion_clara_e_identificadores_solo_del_contexto():
    assert "gramaticalmente correcto" in INSTRUCCIONES_SISTEMA
    assert "identificador exacto" in INSTRUCCIONES_SISTEMA and "No inventes identificadores" in INSTRUCCIONES_SISTEMA
    assert "reembolso" not in INSTRUCCIONES_SISTEMA.lower()  # nada específico del escenario B
    mensajes = construir_prompt("¿Qué hace `x`?", "[1] dato").to_messages()
    assert mensajes[1].content.endswith("Pregunta: ¿Qué hace `x`?")


# --- Actualización incremental de un documento editado ----------------------------------

def test_plan_y_poda_solo_afectan_chunks_del_documento_editado(tmp_path):
    config = CONFIG_BLOQUE26_MD.con(directorio=tmp_path / "vs", modelo_embeddings="simulado/bolsa")
    otra = config.con(nombre_coleccion="otra_coleccion")
    documentos = cargar_documentos(MANIFIESTO_BLOQUE24)
    chunks = dividir_documentos(documentos, "markdown", 200, 30)
    indexar(chunks, config, EmbeddingsSimuladasBolsaPalabras())
    indexar(chunks, otra, EmbeddingsSimuladasBolsaPalabras())
    assert planificar_indexacion(chunks, config)["nuevos"] == []

    editados = [Document(page_content=d.page_content.replace("Gemini", "Gemini (editado)", 1)
                         if d.metadata["fuente"] == "README.md" else d.page_content, metadata=d.metadata)
                for d in documentos]
    nuevos_chunks = dividir_documentos(editados, "markdown", 200, 30)
    plan = planificar_indexacion(nuevos_chunks, config)
    assert plan["fuentes_con_nuevos"] == ["README.md"] and len(plan["nuevos"]) == len(plan["huerfanos"]) >= 1
    assert all(h.startswith("readme-md:") for h in plan["huerfanos"])

    simulados = EmbeddingsSimuladasBolsaPalabras()
    resultado = indexar(nuevos_chunks, config, simulados, podar_huerfanos=True)
    assert resultado.agregados == len(plan["nuevos"]) and resultado.podados == len(plan["huerfanos"])
    assert contar_chunks(config) == len(nuevos_chunks)
    assert contar_chunks(otra) == len(chunks)  # la otra colección no se tocó
    sin_poda = indexar(nuevos_chunks, otra, EmbeddingsSimuladasBolsaPalabras())
    assert sin_poda.podados == 0 and contar_chunks(otra) == len(chunks) + sin_poda.agregados


# --- Conjuntos de evaluación ------------------------------------------------------------

def test_conjunto_de_desarrollo_intacto_y_validacion_separada():
    desarrollo = cargar_consultas(ARCHIVO_CONSULTAS)
    validacion = cargar_consultas(ARCHIVO_VALIDACION)
    assert [c.id for c in desarrollo] == ["reintentos-A", "reintentos-2", "costos-B2", "costos-2", "supervision-B",
                                         "supervision-2", "supervision-3", "fuera-C", "fuera-2"]
    assert sum(bool(c.fuentes) for c in desarrollo) == 7
    assert not {c.id for c in desarrollo} & {c.id for c in validacion}
    assert not {c.pregunta for c in desarrollo} & {c.pregunta for c in validacion}
    assert sum(bool(c.fuentes) for c in validacion) >= 5 and any(not c.fuentes for c in validacion)
    assert "no es una evaluación independiente" in json.loads(ARCHIVO_VALIDACION.read_text(encoding="utf-8"))["descripcion"]
