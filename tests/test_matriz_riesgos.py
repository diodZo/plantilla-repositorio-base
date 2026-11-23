"""Bloque 32: matriz de riesgos, fórmula y cortes oficiales, sensibilidad y supervisión. Offline."""
from __future__ import annotations

import json
import re

import pytest

from src.gobernanza.matriz_riesgos import (
    CATEGORIAS_CON_SUPERVISION, RUTA_MATRIZ, MatrizInvalidaError, calcular_puntaje, cargar_matriz, categoria_riesgo,
    esta_en_el_limite, ordenar, sin_supervision_requerida, tabla_markdown, validar_valor, vecinos_que_cambian,
)
from src.rag.configuracion import RAIZ_REPO


@pytest.mark.parametrize("puntaje, categoria", [
    (1, "BAJO"), (3, "BAJO"), (4, "MEDIO"), (8, "MEDIO"), (9, "ALTO"), (14, "ALTO"), (15, "CRITICO"), (25, "CRITICO")])
def test_cortes_oficiales(puntaje, categoria):
    assert categoria_riesgo(puntaje) == categoria


@pytest.mark.parametrize("valor", [0, 6, -1, True, False, 2.0, "3", None])
def test_valores_invalidos(valor):
    with pytest.raises(ValueError):
        validar_valor(valor)
    with pytest.raises(ValueError):
        calcular_puntaje(valor, 3)
    with pytest.raises(ValueError):
        esta_en_el_limite(3, valor)


def test_puntaje_es_producto():
    assert calcular_puntaje(3, 4) == 12 and calcular_puntaje(1, 1) == 1 and calcular_puntaje(5, 5) == 25


def _limite_fuerza_bruta(p, i):
    base = categoria_riesgo(p * i)
    for np_, ni in ((p - 1, i), (p + 1, i), (p, i - 1), (p, i + 1)):
        if 1 <= np_ <= 5 and 1 <= ni <= 5 and categoria_riesgo(np_ * ni) != base:
            return True
    return False


@pytest.mark.parametrize("p", range(1, 6))
@pytest.mark.parametrize("i", range(1, 6))
def test_sensibilidad_coincide_con_fuerza_bruta(p, i):
    assert esta_en_el_limite(p, i) == _limite_fuerza_bruta(p, i)


@pytest.mark.parametrize("p, i, esperado", [
    (1, 1, False),   # 1×1: subir a 2 sigue BAJO
    (5, 5, False),   # 5×5: bajar a 20 sigue CRITICO
    (4, 5, False), (5, 4, False),
    (2, 2, True),    # corte 4: bajar a 2 → BAJO
    (1, 3, True),    # 3 → subir impacto a 4 cruza el corte 4
    (3, 3, True),    # corte 9: bajar a 6 → MEDIO
    (2, 4, True),    # 8 → subir probabilidad a 12 cruza el corte 9
    (5, 3, True),    # corte 15: bajar a 12 → ALTO
    (3, 4, True),    # 12 → subir a 16 cruza el corte 15
])
def test_casos_de_limite(p, i, esperado):
    assert esta_en_el_limite(p, i) is esperado


def test_vecinos_no_salen_del_rango():
    for cambio in vecinos_que_cambian(1, 5) + vecinos_que_cambian(5, 1):
        assert 1 <= cambio["probabilidad"] <= 5 and 1 <= cambio["impacto"] <= 5
    assert vecinos_que_cambian(5, 5) == [] and vecinos_que_cambian(1, 1) == []


# --- Matriz del proyecto ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def riesgos():
    return cargar_matriz()


def test_al_menos_cinco_riesgos_validos(riesgos):
    assert 6 <= len(riesgos) <= 8
    assert all(1 <= r.probabilidad <= 5 and 1 <= r.impacto <= 5 for r in riesgos)
    assert all(r.puntaje == r.probabilidad * r.impacto and r.categoria == categoria_riesgo(r.puntaje) for r in riesgos)


def test_orden_descendente(riesgos):
    puntajes = [r.puntaje for r in ordenar(riesgos)]
    assert puntajes == sorted(puntajes, reverse=True)


def test_altos_y_criticos_tienen_supervision(riesgos):
    altos = [r for r in riesgos if r.categoria in CATEGORIAS_CON_SUPERVISION]
    assert altos and sin_supervision_requerida(riesgos) == []
    assert all(r.supervision["control"] and r.supervision["estado"] for r in altos)


def test_evidencia_existe_y_vinculada_a_bloques_anteriores(riesgos):
    for r in riesgos:
        assert all((RAIZ_REPO / e["ruta"]).exists() for e in r.evidencia)
        assert all(isinstance(b, int) and 12 <= b <= 32 for b in r.bloques)
    assert any(b < 32 for r in riesgos for b in r.bloques)


def test_distingue_controles_implementados_y_propuestos(riesgos):
    por_id = {r.id: r for r in riesgos}
    assert por_id["R06"].supervision["estado"] == "implementado_probado"
    assert por_id["R01"].supervision["estado"] == "propuesto"  # la cuarentena no se revisa ni detiene la consulta
    assert "brecha pendiente" in por_id["R01"].limitaciones
    controles_probados = [r for r in riesgos if r.supervision["estado"] == "implementado_probado"]
    for r in controles_probados:
        for prueba in re.findall(r"tests/\w+\.py", r.supervision.get("evidencia", "")):
            assert (RAIZ_REPO / prueba).exists(), prueba


def test_puntaje_almacenado_se_rechaza(tmp_path):
    datos = json.loads(RUTA_MATRIZ.read_text(encoding="utf-8"))
    datos["riesgos"][0]["puntaje"] = 25
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(MatrizInvalidaError, match="se calcula"):
        cargar_matriz(ruta)


@pytest.mark.parametrize("campo, valor", [("probabilidad", True), ("impacto", 6), ("probabilidad", 2.5),
                                          ("estado_control", "listo"), ("evidencia", [{"ruta": "no/existe.py", "detalle": "x"}])])
def test_matriz_invalida(tmp_path, campo, valor):
    datos = json.loads(RUTA_MATRIZ.read_text(encoding="utf-8"))
    datos["riesgos"][0][campo] = valor
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(MatrizInvalidaError):
        cargar_matriz(ruta)


def test_menos_de_cinco_riesgos(tmp_path):
    datos = json.loads(RUTA_MATRIZ.read_text(encoding="utf-8"))
    datos["riesgos"] = datos["riesgos"][:4]
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(MatrizInvalidaError, match="al menos 5"):
        cargar_matriz(ruta)


def test_documento_contiene_la_tabla_calculada(riesgos):
    documento = (RAIZ_REPO / "docs" / "matriz_riesgos_bloque32.md").read_text(encoding="utf-8")
    assert tabla_markdown(riesgos) in documento


def test_cli_matriz(capsys):
    from src.matriz_riesgos import main

    assert main([]) == 0
    assert "sin control humano identificado: ninguno" in capsys.readouterr().out
    assert main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["puntaje"] == 12
