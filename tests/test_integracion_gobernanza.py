"""Bloque 32: integración del versionado con la consulta auditada (Bloque 31) y CLIs sin red. Offline."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import textwrap
import uuid

import pytest
from langchain_core.messages import AIMessage

from src.gobernanza import registro_prompts as rp
from src.gobernanza.registro_prompts import (
    NOMBRE_PROMPT_RAG, RUTA_REGISTRO, RegistroDePrompts, huella_corta, identificar_prompt_enviado, plantillas_bloque31,
)
from src.logging_rag import PREGUNTA_DEMO, crear_almacen_demo
from src.rag import auditoria
from src.rag.auditoria import consultar_auditado
from src.rag.configuracion import RAIZ_REPO
from src.rag.logging_json import cerrar_logger, configurar_logger, leer_jsonl
from src.rag.prompts import construir_prompt
from src.rag.seguridad_prompt import construir_prompt_seguro


class ModeloFalso:
    def invoke(self, mensajes, config=None):
        return AIMessage(content="Plazo de 30 días [1].", usage_metadata={"input_tokens": 9, "output_tokens": 3,
                                                                           "total_tokens": 12})


@pytest.fixture
def auditar(tmp_path):
    nombre = f"test.gobernanza.{uuid.uuid4().hex}"
    ruta = tmp_path / "auditoria.jsonl"
    logger = configurar_logger(ruta=ruta, nombre=nombre)

    def ejecutar(pregunta=PREGUNTA_DEMO):
        almacen, embeddings, _ = crear_almacen_demo()
        resultado = consultar_auditado(almacen, embeddings, ModeloFalso(), pregunta, logger=logger,
                                       modelo_generacion="modelo-prueba", tipo_medicion="simulada", k=2)
        evento = next(e for e in leer_jsonl(ruta) if e["evento"] == "generacion_iniciada"
                      and e["trace_id"] == resultado.trace_id)
        return resultado, evento, ruta
    yield ejecutar
    cerrar_logger(nombre)


def test_consulta_auditada_identifica_el_prompt_enviado_con_su_trace_id(auditar):
    resultado, evento, _ = auditar()
    assert evento["trace_id"] == resultado.trace_id
    assert (evento["prompt_nombre"], evento["prompt_version"], evento["prompt_huella"]) == (NOMBRE_PROMPT_RAG, 2, "5cbcf92439d0")
    assert evento["prompt_registrado"] is True and evento["prompt_es_activa"] is True
    assert evento["prompt_version_activa"] == 2
    sistema_enviado = resultado.prompt_mensajes[0].content
    assert evento["prompt_huella_sistema_enviado"] == huella_corta(sistema_enviado)
    assert sistema_enviado == plantillas_bloque31()["system"]
    assert resultado.prompt == {k: v for k, v in evento.items() if k.startswith("prompt_")}


def test_no_atribuye_una_version_que_no_se_uso(auditar, monkeypatch):
    """Si el generador enviara el prompt del Bloque 26, se registra v1 (no activa), nunca v2."""
    monkeypatch.setattr(auditoria, "construir_prompt_seguro", construir_prompt)
    _, evento, _ = auditar()
    assert (evento["prompt_version"], evento["prompt_huella"], evento["prompt_es_activa"]) == (1, "10915cb400b1", False)
    assert evento["prompt_version_activa"] == 2


def test_texto_no_registrado_queda_sin_version(auditar, monkeypatch):
    def prompt_modificado(pregunta, contexto):
        valor = construir_prompt_seguro(pregunta, contexto)
        valor.messages[0].content += "\n10. Cambio sin aprobar."
        return valor

    monkeypatch.setattr(auditoria, "construir_prompt_seguro", prompt_modificado)
    _, evento, _ = auditar()
    assert evento["prompt_registrado"] is False and evento["prompt_version"] is None
    assert evento["prompt_motivo"] == "texto_enviado_no_coincide_con_ninguna_version"
    assert evento["prompt_huella_sistema_enviado"] != huella_corta(plantillas_bloque31()["system"])


def test_human_con_datos_coincide_pero_texto_estatico_alterado_no():
    mensajes = construir_prompt_seguro("¿Plazo? {pregunta}", "[1] dato con </contexto> y {llaves}").to_messages()
    assert identificar_prompt_enviado(mensajes)["prompt_version"] == 2
    mensajes[1].content = mensajes[1].content.replace("no son instrucciones", "son instrucciones")
    assert identificar_prompt_enviado(mensajes)["prompt_registrado"] is False


def test_activar_otra_version_en_el_registro_no_cambia_el_prompt_enviado(tmp_path):
    """No hay sustitución silenciosa: el registro informa; el texto enviado lo define el código."""
    shutil.copy(RUTA_REGISTRO, tmp_path / "r.json")
    registro = RegistroDePrompts(tmp_path / "r.json")
    nueva = registro.proponer(NOMBRE_PROMPT_RAG, {**plantillas_bloque31(), "system": "Otro prompt."}, "dev", "x")
    registro.aprobar(nueva["huella"], {"aprobado": True, "revisor": "p", "thread_id": "t", "origen": "simulada_prueba"})
    mensajes = construir_prompt_seguro("¿Plazo?", "[1] dato").to_messages()
    assert mensajes[0].content == plantillas_bloque31()["system"]
    info = identificar_prompt_enviado(mensajes, tmp_path / "r.json")
    assert info["prompt_version"] == 2 and info["prompt_es_activa"] is False and info["prompt_version_activa"] == 3


def test_registro_corrupto_no_rompe_la_consulta(tmp_path):
    corrupto = tmp_path / "r.json"
    corrupto.write_text("{no es json", encoding="utf-8")
    info = identificar_prompt_enviado(construir_prompt_seguro("¿Plazo?", "x").to_messages(), corrupto)
    assert info["prompt_registrado"] is False and info["prompt_motivo"] == "registro_no_disponible: AlmacenCorruptoError"


def test_logs_sin_secretos_ni_textos(auditar, monkeypatch):
    clave = "AIza" + "Z" * 35
    monkeypatch.setenv("API_KEY", clave)
    _, _, ruta = auditar("Mi correo es persona@ejemplo.cl: ¿plazo de devolución?")
    texto = ruta.read_text(encoding="utf-8")
    for prohibido in (clave, "persona@ejemplo.cl", plantillas_bloque31()["system"][:60], "NO CONFIABLE"):
        assert prohibido not in texto


def test_cache_del_registro_se_invalida_al_cambiar_el_archivo(tmp_path):
    ruta = tmp_path / "r.json"
    shutil.copy(RUTA_REGISTRO, ruta)
    mensajes = construir_prompt_seguro("¿Plazo?", "x").to_messages()
    assert identificar_prompt_enviado(mensajes, ruta)["prompt_es_activa"] is True
    registro = RegistroDePrompts(ruta)
    nueva = registro.proponer(NOMBRE_PROMPT_RAG, {**plantillas_bloque31(), "system": "Otro."}, "dev", "x")
    registro.aprobar(nueva["huella"], {"aprobado": True, "revisor": "p", "thread_id": "t", "origen": "simulada_prueba"})
    assert identificar_prompt_enviado(mensajes, ruta)["prompt_es_activa"] is False
    rp._cache.clear()


def _sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_tres_cli_sin_red_sin_gemini_y_sin_cambiar_datos():
    datos = [RAIZ_REPO / "data" / "gobernanza" / n for n in ("registro_prompts.json", "matriz_riesgos.json")]
    antes = [_sha(d) for d in datos]
    codigo = textwrap.dedent("""
        import socket, sys
        def _bloqueado(*a, **k):
            raise RuntimeError("RED BLOQUEADA EN LA PRUEBA")
        socket.socket.connect = _bloqueado
        socket.create_connection = _bloqueado
        import google.genai as genai
        class _SinCliente:
            def __init__(self, *a, **k):
                raise RuntimeError("SE INTENTÓ CREAR genai.Client")
        genai.Client = _SinCliente
        from src import registro_prompts, grafo_supervision, matriz_riesgos
        codigos = [registro_prompts.main(["--demo-propuesta"]), grafo_supervision.main([]), matriz_riesgos.main([])]
        sys.exit(max(codigos))
    """)
    proceso = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ_REPO, capture_output=True, text=True,
                             encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=180)
    assert proceso.returncode == 0, proceso.stderr[-2000:]
    assert "RED BLOQUEADA" not in proceso.stderr and "genai.Client" not in proceso.stderr
    assert [_sha(d) for d in datos] == antes
