"""Gate 2: rúbrica ponderada y criterios no compensables (autoevaluación). Offline."""
from __future__ import annotations

import json

import pytest

from src import rubrica_gate2 as rb

TODOS_OK = {n: True for n in rb.NO_COMPENSABLES}


def puntajes(valor=90, **cambios):
    return {**{d: valor for d in rb.PESOS_GATE2}, **cambios}


def test_pesos_exactos_del_curso():
    assert rb.PESOS_GATE2 == {"pipeline_funcional": 0.25, "recuperacion_citacion": 0.15, "costo_latencia": 0.10,
                              "personalizacion": 0.15, "observabilidad": 0.15, "seguridad_gobernanza": 0.20}
    assert sum(rb.PESOS_GATE2.values()) == pytest.approx(1.0) and rb.UMBRAL_APROBACION == 80


def test_promedio_ponderado():
    p = {"pipeline_funcional": 80, "recuperacion_citacion": 60, "costo_latencia": 100, "personalizacion": 70,
         "observabilidad": 90, "seguridad_gobernanza": 50}
    assert rb.promedio_ponderado(p) == pytest.approx(80 * .25 + 60 * .15 + 100 * .10 + 70 * .15 + 90 * .15 + 50 * .20)


def test_listo_para_revision_solo_si_todo_se_cumple():
    informe = rb.evaluar(puntajes(85), TODOS_OK)
    assert informe["estado"] == "LISTO_PARA_REVISION" and informe["evaluacion_oficial"] is None
    assert informe["tipo"] == "autoevaluacion"


@pytest.mark.parametrize("criterio", list(rb.NO_COMPENSABLES))
def test_no_compensable_fallido_bloquea_aunque_el_promedio_sea_alto(criterio):
    informe = rb.evaluar(puntajes(100), {**TODOS_OK, criterio: False})
    assert informe["estado"] == "PENDIENTE" and criterio in informe["motivo"]


@pytest.mark.parametrize("criterio", list(rb.NO_COMPENSABLES))
def test_no_compensable_sin_verificar(criterio):
    assert rb.evaluar(puntajes(100), {**TODOS_OK, criterio: None})["estado"] == "NO_VERIFICADO"


def test_promedio_bajo_y_dimension_pendiente():
    assert rb.evaluar(puntajes(79), TODOS_OK)["estado"] == "PENDIENTE"
    informe = rb.evaluar(puntajes(100, observabilidad=None), TODOS_OK)
    assert informe["estado"] == "PENDIENTE" and informe["promedio"] is None
    assert informe["dimensiones_pendientes"] == ["observabilidad"]


@pytest.mark.parametrize("valor", [True, -1, 101, 85.5, "90"])
def test_puntajes_invalidos(valor):
    with pytest.raises(ValueError):
        rb.promedio_ponderado(puntajes(90, costo_latencia=valor))


def test_entradas_incompletas():
    with pytest.raises(ValueError):
        rb.promedio_ponderado({"pipeline_funcional": 90})
    with pytest.raises(ValueError):
        rb.evaluar(puntajes(90), {"pipeline_punta_a_punta": True})
    with pytest.raises(ValueError):
        rb.evaluar(puntajes(90), {**TODOS_OK, "logs_sin_contenido_crudo": "sí"})


def test_nunca_declara_aprobacion_oficial():
    estados = {rb.evaluar(puntajes(v), nc)["estado"] for v in (0, 79, 80, 100)
               for nc in (TODOS_OK, {**TODOS_OK, "pipeline_punta_a_punta": None})}
    assert estados <= set(rb.ESTADOS) and "GATE_APROBADO_OFICIALMENTE" not in estados


def test_autoevaluacion_del_proyecto_valida_y_con_evidencia():
    datos = rb.cargar_autoevaluacion()
    assert datos["evaluacion_oficial"] is None
    for dimension in rb.PESOS_GATE2:
        assert datos["dimensiones"][dimension]["evidencia"] and datos["dimensiones"][dimension]["justificacion"]


def test_autoevaluacion_que_se_declara_oficial_se_rechaza(tmp_path):
    datos = json.loads(rb.RUTA_AUTOEVALUACION.read_text(encoding="utf-8"))
    datos["evaluacion_oficial"] = "aprobado"
    ruta = tmp_path / "a.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError):
        rb.cargar_autoevaluacion(ruta)


def test_cli_sin_pruebas_queda_no_verificado(capsys):
    assert rb.main(["--sin-pruebas"]) == 1
    assert "Estado: NO_VERIFICADO" in capsys.readouterr().out
