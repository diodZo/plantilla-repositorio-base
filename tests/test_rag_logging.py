"""Bloque 31: JsonFormatter, saneado de secretos, huella y configuración de handlers. Offline."""
from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timezone

import pytest

from src.rag.logging_json import (
    JsonFormatter, cerrar_logger, configurar_logger, huella, leer_jsonl, registrar_evento, sanear,
)
from src.rag.trazabilidad import contexto_traza


@pytest.fixture
def logger_memoria():
    nombre = f"test.logging.{uuid.uuid4().hex}"
    flujo = io.StringIO()
    logger = configurar_logger(stream=flujo, nombre=nombre)
    yield logger, flujo
    cerrar_logger(nombre)


def lineas(flujo: io.StringIO) -> list[dict]:
    return [json.loads(l) for l in flujo.getvalue().splitlines() if l.strip()]


def test_evento_es_json_de_una_linea_con_campos_minimos(logger_memoria):
    logger, flujo = logger_memoria
    with contexto_traza("trace-prueba"):
        registrar_evento(logger, "consulta_recibida", pregunta_len=45)
    texto = flujo.getvalue()
    assert texto.count("\n") == 1
    [evento] = lineas(flujo)
    assert evento["level"] == "INFO" and evento["evento"] == "consulta_recibida"
    assert evento["trace_id"] == "trace-prueba" and evento["pregunta_len"] == 45
    ts = datetime.fromisoformat(evento["ts"])
    assert ts.tzinfo is not None and ts.utcoffset() == timezone.utc.utcoffset(None)
    assert evento["ts"].endswith("+00:00")


def test_unicode_y_saltos_de_linea_escapados(logger_memoria):
    logger, flujo = logger_memoria
    registrar_evento(logger, "prueba_unicode", fuente="guía/año_ñandú.md", nota="línea 1\nlínea 2 ✓ 漢字")
    assert flujo.getvalue().count("\n") == 1
    assert "guía/año_ñandú.md" in flujo.getvalue()  # UTF-8 sin escapar
    [evento] = lineas(flujo)
    assert evento["nota"] == "línea 1\nlínea 2 ✓ 漢字"


def test_sin_trace_activo_es_null(logger_memoria):
    logger, flujo = logger_memoria
    registrar_evento(logger, "fuera_de_consulta")
    assert lineas(flujo)[0]["trace_id"] is None


def test_datos_no_sobrescriben_campos_base(logger_memoria):
    logger, flujo = logger_memoria
    with contexto_traza("trace-real"):
        logger.info("x", extra={"evento": "e", "datos": {"trace_id": "falso", "level": "DEBUG", "ts": "ayer"}})
    evento = lineas(flujo)[0]
    assert evento["trace_id"] == "trace-real" and evento["level"] == "INFO" and evento["ts"] != "ayer"


def test_no_registra_secretos(logger_memoria):
    logger, flujo = logger_memoria
    clave = "AIza" + "S" * 35
    registrar_evento(logger, "config", api_key=clave, GOOGLE_API_KEY=clave, detalle=f"falló con key={clave}",
                     anidado={"password": "x", "fuentes": ["a.md"]})
    texto = flujo.getvalue()
    assert clave not in texto and '"x"' not in texto
    evento = lineas(flujo)[0]
    assert evento["api_key"] == "<oculto>" and evento["GOOGLE_API_KEY"] == "<oculto>"
    assert "<clave oculta>" in evento["detalle"] and evento["anidado"]["fuentes"] == ["a.md"]


def test_excepcion_solo_registra_el_tipo(logger_memoria):
    logger, flujo = logger_memoria
    try:
        raise ValueError("mensaje con dato sensible 12345")
    except ValueError:
        logger.error("fallo", exc_info=True, extra={"evento": "fallo", "datos": {}})
    assert "12345" not in flujo.getvalue()
    assert lineas(flujo)[0]["excepcion_tipo"] == "ValueError"


def test_sanear_tipos_varios():
    assert sanear({"a": (1, None, True), "Authorization": "Bearer x"}) == {"a": [1, None, True], "Authorization": "<oculto>"}


def test_huella_sha256_determinista_y_sin_texto():
    a = huella("¿Cuál es mi saldo?")
    assert a == huella("¿Cuál es mi saldo?") and a != huella("¿Cuál es mi saldo")
    assert a.startswith("sha256:") and len(a) == len("sha256:") + 16 and "saldo" not in a
    with pytest.raises(TypeError):
        huella(None)
    with pytest.raises(ValueError):
        huella("x", longitud=4)


def test_huella_de_texto_previsible_es_recuperable_por_diccionario():
    """Documenta la limitación: una huella NO anonimiza textos previsibles."""
    objetivo = huella("sí")
    diccionario = ["no", "sí", "tal vez"]
    assert [p for p in diccionario if huella(p) == objetivo] == ["sí"]


def test_configurar_dos_veces_no_duplica_handlers(tmp_path):
    nombre = f"test.dup.{uuid.uuid4().hex}"
    ruta = tmp_path / "logs" / "auditoria.jsonl"
    try:
        logger = configurar_logger(ruta=ruta, nombre=nombre)
        configurar_logger(ruta=ruta, nombre=nombre)
        configurar_logger(ruta=str(ruta), nombre=nombre)
        assert len(logger.handlers) == 1 and logger.propagate is False
        registrar_evento(logger, "uno")
        registrar_evento(logger, "dos")
    finally:
        cerrar_logger(nombre)
    eventos = leer_jsonl(ruta)
    assert [e["evento"] for e in eventos] == ["uno", "dos"]
    assert ruta.read_bytes().decode("utf-8")  # UTF-8 válido
    assert logging.getLogger(nombre).handlers == []


def test_formatter_directo_con_logrecord():
    registro = logging.LogRecord("x", logging.WARNING, __file__, 1, "evento_directo", None, None)
    evento = json.loads(JsonFormatter().format(registro))
    assert evento["evento"] == "evento_directo" and evento["level"] == "WARNING"
