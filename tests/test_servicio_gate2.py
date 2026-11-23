"""Gate 2: contrato de respuesta, modelo simulado, rutas heredadas y preflight. Offline."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

import pytest

from src import preflight_gate2 as pf
from src.rag.preflight import ERROR, OK
from src.servicio_rag import RUTAS_HEREDADAS, ModeloSimulado, RespuestaServicio, ServicioRAG


def test_contrato_serializable_con_campos_obligatorios():
    respuesta = RespuestaServicio("r [1]", [{"numero": 1, "documento": "a.md"}], "trace-x", "respondida", None,
                                  "simulado", 2, "5cbcf92439d0", {"input_tokens": None, "output_tokens": None,
                                                                   "total_tokens": None}, "simulada", 1.0, None)
    datos = respuesta.como_dict()
    for campo in ("respuesta", "fuentes", "trace_id", "estado", "modo", "prompt_version", "tokens",
                  "tiempo_total_ms", "costo_estimado_usd", "medicion", "motivo"):
        assert campo in datos
    assert datos["fuentes_contexto"] == [] and datos["unidades_descartadas"] == 0


def test_modo_invalido():
    with pytest.raises(ValueError):
        ServicioRAG(None, None, None, None, modo="produccion", modelo_generacion="m", modelo_embeddings="e")


def test_modelo_simulado_responde_con_el_fragmento_1_y_lo_marca():
    modelo = ModeloSimulado()
    mensajes = [SystemMessage(content="reglas"), HumanMessage(
        content="<contexto>\n[1] [Doc > Sección]\nPrimera oración. Segunda oración.\n\n[2] Otro.\n</contexto>\nPregunta: x")]
    respuesta = modelo.invoke(mensajes)
    assert respuesta.content == "[SIMULADO] Según la documentación: Primera oración. [1]"
    assert respuesta.usage_metadata["total_tokens"] == respuesta.usage_metadata["input_tokens"] + \
        respuesta.usage_metadata["output_tokens"]
    vacio = modelo.invoke([SystemMessage(content="s"), HumanMessage(content="<contexto>\n\n</contexto>")])
    assert "no contiene información suficiente" in vacio.content and modelo.llamadas == 2
    assert ModeloSimulado(uso=False).invoke(mensajes).usage_metadata is None


def test_rutas_heredadas_identificadas_en_codigo():
    from pathlib import Path

    from src.rag.configuracion import RAIZ_REPO
    assert set(RUTAS_HEREDADAS) == {"src.rag.generador.responder", "src.recuperar_corpus", "src.registro_rag",
                                    "src.evaluar_bloque27"}
    for archivo in ("src/recuperar_corpus.py", "src/registro_rag.py", "src/evaluar_bloque27.py", "src/rag/generador.py"):
        assert "RUTA HEREDADA" in Path(RAIZ_REPO / archivo).read_text(encoding="utf-8")


def test_preflight_python_y_requisitos():
    assert pf.comprobar_python()[0].nivel == OK
    requisitos = dict(pf.requisitos())
    assert requisitos["langgraph"] == "1.2.19" and requisitos["chromadb"] == "1.5.9" and requisitos["pytest"] is None
    assert all(r.nivel != ERROR for r in pf.comprobar_dependencias())


def test_preflight_detecta_secretos_sin_mostrarlos(tmp_path):
    limpio, sucio = tmp_path / "limpio.md", tmp_path / "sucio.py"
    limpio.write_text("API_KEY=coloca_aqui_tu_clave_real\nUsa obtener_clave_api()", encoding="utf-8")
    clave = "AIza" + "K" * 35
    sucio.write_text(f'clave = "{clave}"', encoding="utf-8")
    assert pf.buscar_secretos([limpio, sucio]) == [str(sucio)]


def test_preflight_archivos_faltantes(tmp_path):
    [resultado] = pf.comprobar_archivos(tmp_path, ("no_existe.md",), "documentación")
    assert resultado.nivel == ERROR and "no_existe.md" in resultado.mensaje


def test_preflight_gobernanza_valida():
    assert all(r.nivel == OK for r in pf.comprobar_gobernanza())
