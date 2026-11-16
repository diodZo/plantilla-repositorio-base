"""Bloque 28: tokens y costos (sin red)."""
import json
import math

import pytest
from langchain_core.messages import AIMessage

from src.rag.costos import (
    ARCHIVO_TARIFAS, Tarifa, buscar_tarifa, calcular_costo, cargar_tarifas, costo_por_tokens, desglose_costo,
    estimar_tokens_por_caracteres, extraer_uso,
)

TARIFA_GEN = Tarifa("modelo-x", 0.30, 2.50, "fuente", "2026-11-16", "verificada")
TARIFA_EMB = Tarifa("models/emb", 0.15, None, "fuente", "2026-11-16", "verificada")


def test_calcular_costo_formula():
    # 1000 × 0,30 / 1e6 + 500 × 2,50 / 1e6 = 0,0003 + 0,00125
    assert calcular_costo(1000, 500, 0.30, 2.50) == pytest.approx(0.00155)
    assert calcular_costo(0, 0, 0.30, 2.50) == 0.0
    assert costo_por_tokens(2_000_000, 0.15) == pytest.approx(0.30)


@pytest.mark.parametrize("args", [(None, 10, 0.3, 2.5), (10, None, 0.3, 2.5), (10, 10, None, 2.5), (10, 10, 0.3, None)])
def test_tokens_o_tarifas_faltantes_dan_none(args):
    assert calcular_costo(*args) is None


@pytest.mark.parametrize("args", [(-1, 0, 0.3, 2.5), (1, 1, -0.3, 2.5), (True, 1, 0.3, 2.5), (1, 1, math.nan, 2.5), ("1", 1, 0.3, 2.5)])
def test_valores_invalidos(args):
    with pytest.raises(ValueError):
        calcular_costo(*args)


def test_extraer_uso_real_con_razonamiento_y_otros():
    mensaje = AIMessage(content=[{"type": "text", "text": "Hola [1]"}], usage_metadata={
        "input_tokens": 900, "output_tokens": 120, "total_tokens": 1030,
        "input_token_details": {"cache_read": 0}, "output_token_details": {"reasoning": 80}})
    uso = extraer_uso(mensaje)
    assert uso == {"estado": "reportado", "entrada": 900, "salida": 120, "total": 1030,
                   "razonamiento": 80, "cache_lectura": 0, "otros": 10}   # no se asume total = entrada + salida


def test_extraer_uso_sin_metadatos():
    uso = extraer_uso(AIMessage(content="sin uso"))
    assert uso["estado"] == "no_disponible" and uso["entrada"] is None and uso["total"] is None


def test_desglose_distingue_calculado_estimado_y_desconocido():
    uso = {"estado": "reportado", "entrada": 1000, "salida": 500, "cache_lectura": 0}
    d = desglose_costo(uso, TARIFA_GEN, "¿pregunta de doce?", TARIFA_EMB)
    assert d["generacion"]["total_usd"] == pytest.approx(0.00155)
    assert d["generacion"]["estado"].startswith("calculado")
    assert d["total_conocido_usd"] == d["generacion"]["total_usd"]               # el embedding no se suma
    assert d["embedding_consulta"]["estado"] == "estimado"
    assert d["embedding_consulta"]["metodo"] == "caracteres/4"
    assert any("facturado" in n for n in d["no_incluido"])

    sin_tarifa = desglose_costo(uso, None, "x", None)
    assert sin_tarifa["total_conocido_usd"] is None and "sin tarifa" in sin_tarifa["generacion"]["estado"]
    assert sin_tarifa["embedding_consulta"]["costo_estimado_usd"] is None
    sin_tokens = desglose_costo({"estado": "no_disponible"}, TARIFA_GEN, "x", TARIFA_EMB)
    assert sin_tokens["total_conocido_usd"] is None and "no reportados" in sin_tokens["generacion"]["estado"]
    con_cache = desglose_costo(uso | {"cache_lectura": 300}, TARIFA_GEN, "x", TARIFA_EMB)
    assert any("caché" in n for n in con_cache["no_incluido"])


def test_estimacion_por_caracteres_es_explicita():
    assert estimar_tokens_por_caracteres("abcde") == 2
    assert estimar_tokens_por_caracteres("") == 0


def test_cargar_tarifas_y_buscar_por_nombre(tmp_path):
    ruta = tmp_path / "t.json"
    ruta.write_text(json.dumps({"tipo": "ilustrativa", "fuente": "ejemplo", "fecha_consulta": "2026-01-01",
                                "modelos": {"m1": {"entrada": 1.0, "salida": 2.0}, "models/e": {"entrada": 0.1, "salida": None}}}),
                    encoding="utf-8")
    tarifas = cargar_tarifas(ruta)
    assert tarifas["m1"].tipo == "ilustrativa"
    assert buscar_tarifa(tarifas, "models/m1") is tarifas["m1"]
    assert buscar_tarifa(tarifas, "e") is tarifas["models/e"]
    assert buscar_tarifa(tarifas, "otro") is None


@pytest.mark.parametrize("datos", [
    {"tipo": "precio", "fuente": "f", "fecha_consulta": "d", "modelos": {}},
    {"tipo": "verificada", "fecha_consulta": "d", "modelos": {}},
    {"tipo": "verificada", "fuente": "f", "fecha_consulta": "d", "modelos": {"m": {"entrada": -1}}},
])
def test_tarifas_mal_configuradas(tmp_path, datos):
    ruta = tmp_path / "t.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_tarifas(ruta)


def test_archivo_de_tarifas_del_proyecto_tiene_procedencia():
    tarifas = cargar_tarifas(ARCHIVO_TARIFAS)
    gen = buscar_tarifa(tarifas, "gemini-3.5-flash-lite")
    assert gen is not None and gen.fuente.startswith("https://") and gen.fecha_consulta
    assert gen.tipo in ("verificada", "ilustrativa")
