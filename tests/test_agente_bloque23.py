"""Pruebas offline, sin Gemini ni operaciones financieras reales."""
import json
from types import SimpleNamespace

from src.agente_bloque23 import (
    HERRAMIENTA_ALTO_RIESGO, crear_herramienta_supervisada,
    detectar_repeticiones, registrar_traza, esperar_aprobacion,
)


def test_reembolso_simulado_rechazado():
    decisiones = []
    herramienta = crear_herramienta_supervisada(lambda _m, _t: False, registro=decisiones)
    salida = herramienta.invoke({"numero_pedido": "P1", "monto": 200})
    assert "rechazada" in salida
    assert decisiones[0]["aprobado"] is False


def test_reembolso_simulado_aprobado_sin_mover_dinero():
    decisiones = []
    herramienta = crear_herramienta_supervisada(lambda _m, _t: True, registro=decisiones)
    salida = herramienta.invoke({"numero_pedido": "P1", "monto": 200})
    assert "Simulación aprobada" in salida and "No se ejecutó un reembolso real" in salida
    assert decisiones[0]["aprobado"] is True


def test_fallo_del_aprobador_deniega():
    def falla(_mensaje, _tiempo):
        raise EOFError("Sin consola")
    decisiones = []
    herramienta = crear_herramienta_supervisada(falla, registro=decisiones)
    assert "rechazada" in herramienta.invoke({"numero_pedido": "P1", "monto": 200})
    assert decisiones[0]["aprobado"] is False


def test_sin_tty_deniega(monkeypatch):
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert esperar_aprobacion("¿Confirmar?", 0.01) is False


def test_timeout_cero_deniega():
    assert esperar_aprobacion("¿Confirmar?", 0) is False


def test_monto_invalido_no_pide_aprobacion():
    llamadas = []
    def aprueba(_m, _t):
        llamadas.append(1)
        return True
    herramienta = crear_herramienta_supervisada(aprueba)
    assert "inválida" in herramienta.invoke({"numero_pedido": "P1", "monto": -10})
    assert llamadas == []


def test_registrar_traza_unicode_y_sin_intermediate_steps(tmp_path):
    archivo = tmp_path / "trazas.jsonl"
    registro = registrar_traza("sesion1", "¿Qué pasó?", {"output": "Bien, gracias"}, archivo)
    assert registro["acciones"] == []
    datos = json.loads(archivo.read_text(encoding="utf-8").strip())
    assert datos["entrada"] == "¿Qué pasó?"


def test_registrar_traza_y_detectar_repeticiones_consecutivas(tmp_path):
    archivo = tmp_path / "trazas.jsonl"
    acciones = [(SimpleNamespace(tool="buscar", tool_input={"q": "A"}), "obs1"),
                (SimpleNamespace(tool="buscar", tool_input={"q": "B"}), "obs2")]
    registrar_traza("sesion1", "consulta", {"output": "ok", "intermediate_steps": acciones}, archivo)
    alertas = detectar_repeticiones(archivo)
    assert len(alertas) == 1
    assert "consecutivamente" in alertas[0]["motivo"]


def test_no_marca_repeticiones_no_consecutivas(tmp_path):
    archivo = tmp_path / "trazas.jsonl"
    acciones = [(SimpleNamespace(tool=n, tool_input={}), "obs") for n in ("A", "B", "A")]
    registrar_traza("s1", "consulta", {"output": "ok", "intermediate_steps": acciones}, archivo)
    assert detectar_repeticiones(archivo) == []


def test_traza_json_invalido_se_marca(tmp_path):
    archivo = tmp_path / "trazas.jsonl"
    archivo.write_text('{invalido}\n', encoding="utf-8")
    assert detectar_repeticiones(archivo)[0]["motivo"] == "JSON inválido"


def test_herramienta_alto_riesgo_tiene_nombre_explicito():
    herramienta = crear_herramienta_supervisada(lambda _m, _t: False)
    assert herramienta.name == HERRAMIENTA_ALTO_RIESGO
    assert "SIMULACIÓN" in herramienta.description
