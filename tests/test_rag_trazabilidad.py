"""Bloque 31: trace_id con contextvars (incluida concurrencia) y callbacks de LangChain. Offline."""
from __future__ import annotations

import asyncio
import io
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models import FakeListLLM, FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda

from src.rag.callbacks import ManejadorAuditoria, tokens_de_llm_result
from src.rag.logging_json import cerrar_logger, configurar_logger, registrar_evento
from src.rag.trazabilidad import TRACE_ID, contexto_traza, nuevo_trace_id, obtener_trace_id


@pytest.fixture
def logger_memoria():
    nombre = f"test.traza.{uuid.uuid4().hex}"
    flujo = io.StringIO()
    logger = configurar_logger(stream=flujo, nombre=nombre)
    yield logger, flujo
    cerrar_logger(nombre)


def eventos(flujo):
    return [json.loads(l) for l in flujo.getvalue().splitlines() if l.strip()]


# --- ContextVar ----------------------------------------------------------------------------

def test_trace_ids_unicos():
    ids = {nuevo_trace_id() for _ in range(1000)}
    assert len(ids) == 1000 and all(i.startswith("trace-") for i in ids)


def test_contexto_se_establece_y_restaura():
    assert obtener_trace_id() is None
    with contexto_traza() as tid:
        assert obtener_trace_id() == tid
        with contexto_traza("trace-interno"):
            assert obtener_trace_id() == "trace-interno"
        assert obtener_trace_id() == tid
    assert obtener_trace_id() is None


def test_contexto_se_restaura_con_excepcion():
    with pytest.raises(RuntimeError):
        with contexto_traza("trace-falla"):
            raise RuntimeError("etapa rota")
    assert obtener_trace_id() is None


def test_trace_id_invalido():
    with pytest.raises(ValueError):
        with contexto_traza("  "):
            pass


def test_no_es_una_variable_global_compartida():
    assert type(TRACE_ID).__name__ == "ContextVar"


def test_hilos_concurrentes_no_mezclan_ids(logger_memoria):
    logger, flujo = logger_memoria
    barrera = threading.Barrier(8)

    def consulta(n):
        with contexto_traza(f"trace-hilo-{n}") as tid:
            registrar_evento(logger, "inicio", n=n)
            barrera.wait()  # Todos los hilos están dentro de su contexto a la vez.
            registrar_evento(logger, "fin", n=n)
            return tid, obtener_trace_id()

    with ThreadPoolExecutor(8) as ejecutor:
        resultados = list(ejecutor.map(consulta, range(8)))
    assert all(a == b for a, b in resultados)
    for e in eventos(flujo):
        assert e["trace_id"] == f"trace-hilo-{e['n']}"
    assert len(eventos(flujo)) == 16


def test_tareas_asyncio_concurrentes_no_mezclan_ids():
    async def consulta(n):
        with contexto_traza(f"trace-async-{n}"):
            await asyncio.sleep(0.01 * (5 - n))
            return n, obtener_trace_id()

    async def todas():
        return await asyncio.gather(*(consulta(n) for n in range(5)))

    assert all(tid == f"trace-async-{n}" for n, tid in asyncio.run(todas()))


# --- Callbacks ------------------------------------------------------------------------------

class RecuperadorFalso(BaseRetriever):
    documentos: list[Document]
    fallar: bool = False

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun):
        if self.fallar:
            raise ConnectionError("índice inaccesible (simulado)")
        return self.documentos


DOCS = [Document(page_content="Secreto del documento A", metadata={"fuente": "a.md"}),
        Document(page_content="Contenido B", metadata={"fuente": "b.md"})]


def test_callbacks_cadena_retriever_y_llm_con_run_ids(logger_memoria):
    logger, flujo = logger_memoria
    manejador = ManejadorAuditoria(logger)
    cadena = (RecuperadorFalso(documentos=DOCS)
              | RunnableLambda(lambda docs: "Contexto: " + " ".join(d.page_content for d in docs))
              | FakeListLLM(responses=["respuesta falsa [1]"]))
    with contexto_traza("trace-cadena"):
        salida = cadena.invoke("¿pregunta privada?", config={"callbacks": [manejador]})
    assert salida == "respuesta falsa [1]"
    registro = {e["evento"]: e for e in eventos(flujo)}
    assert {"lc_retriever_start", "lc_retriever_end", "lc_llm_start", "lc_llm_end"} <= set(registro)
    assert all(e["trace_id"] == "trace-cadena" for e in registro.values())
    inicio, fin = registro["lc_retriever_start"], registro["lc_retriever_end"]
    assert inicio["run_id"] == fin["run_id"] and inicio["parent_run_id"] is not None
    assert registro["lc_llm_start"]["parent_run_id"] == inicio["parent_run_id"]  # misma cadena padre
    assert registro["lc_llm_start"]["run_id"] != inicio["run_id"]
    assert fin["documentos"] == 2 and fin["fuentes"] == ["a.md", "b.md"]
    assert registro["lc_llm_end"]["respuesta_caracteres"] == len("respuesta falsa [1]")
    assert registro["lc_llm_end"]["total_tokens"] is None  # FakeListLLM no reporta uso
    texto = flujo.getvalue()
    assert "pregunta privada" not in texto and "Secreto del documento" not in texto


def test_callback_chat_model_con_aimessage_y_tokens(logger_memoria):
    logger, flujo = logger_memoria
    modelo = FakeMessagesListChatModel(responses=[AIMessage(
        content="hola [1]", usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13})])
    modelo.invoke("texto del prompt", config={"callbacks": [ManejadorAuditoria(logger)]})
    registro = {e["evento"]: e for e in eventos(flujo)}
    assert registro["lc_chat_model_start"]["roles"] == ["human"]
    assert (registro["lc_llm_end"]["input_tokens"], registro["lc_llm_end"]["output_tokens"],
            registro["lc_llm_end"]["total_tokens"]) == (10, 3, 13)
    assert "texto del prompt" not in flujo.getvalue()


def test_callback_registra_errores_sin_mensaje(logger_memoria):
    logger, flujo = logger_memoria
    manejador = ManejadorAuditoria(logger)
    with pytest.raises(ConnectionError):
        RecuperadorFalso(documentos=[], fallar=True).invoke("q", config={"callbacks": [manejador]})

    class ModeloQueFalla(FakeListLLM):
        def _call(self, *a, **k):
            raise TimeoutError("clave AIza" + "X" * 30)

    with pytest.raises(TimeoutError):
        ModeloQueFalla(responses=["x"]).invoke("q", config={"callbacks": [manejador]})
    registro = {e["evento"]: e for e in eventos(flujo)}
    assert registro["lc_retriever_error"]["error_tipo"] == "ConnectionError"
    assert registro["lc_llm_error"]["error_tipo"] == "TimeoutError" and registro["lc_llm_error"]["level"] == "ERROR"
    assert "AIza" not in flujo.getvalue()


def test_fallo_del_logger_no_rompe_la_cadena():
    class LoggerRoto:
        def log(self, *a, **k):
            raise OSError("disco lleno")

    manejador = ManejadorAuditoria(LoggerRoto())
    assert FakeListLLM(responses=["ok"]).invoke("q", config={"callbacks": [manejador]}) == "ok"
    assert manejador.errores_internos >= 2


def test_tokens_ausentes_quedan_en_none():
    class Vacio:
        generations = []
        llm_output = None
    assert tokens_de_llm_result(Vacio()) == {"input_tokens": None, "output_tokens": None, "total_tokens": None}
