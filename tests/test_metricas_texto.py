import pytest
from src.metricas_texto import (contar_coincidencias, calcular_precision_cobertura_f1,
                               calcular_metricas, resumir_metricas)
from src.ensayo_bloque16 import guardar_resultados, cargar_resultados, ejecutar


def test_coincidencias_consideran_repeticiones():
    assert contar_coincidencias(["el", "gato"], ["el", "gato", "el", "gato"]) == 2


def test_ejemplo_del_material():
    m = calcular_metricas("El gato duerme en el sofá.", "El gato duerme en el sillón todo el día.")
    assert m["precision"] == pytest.approx(5/9)
    assert m["cobertura"] == pytest.approx(5/6)
    assert m["f1"] == pytest.approx(2/3)


@pytest.mark.parametrize("ref,res", [([], ["hola"]), (["hola"], []), ([], [])])
def test_vacios_sin_division_cero(ref, res):
    assert calcular_precision_cobertura_f1(ref, res) == {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}


def test_sinonimos_f1_bajo():
    assert calcular_metricas("El auto es veloz.", "El vehículo es rápido.")["f1"] == pytest.approx(0.5)


def test_fecha_incorrecta_f1_alto():
    assert calcular_metricas("Python fue creado en 1991.", "Python fue creado en 1989.")["f1"] == pytest.approx(.8)


def test_negacion_ausente_f1_alto():
    assert calcular_metricas("Python no es un lenguaje compilado.", "Python es un lenguaje compilado.")["f1"] == pytest.approx(10/11)


def test_resumen_vacio():
    assert resumir_metricas([]) == {"precision_promedio": 0.0, "cobertura_promedio": 0.0, "f1_promedio": 0.0}


def test_persistencia_utf8(tmp_path):
    ruta = tmp_path / "docs" / "resultados_metricas.json"
    datos = [{"consulta": "¿Qué es una API?", "respuesta": "Comunicación", "precision": .5, "cobertura": .6, "f1": .55}]
    guardar_resultados(ruta, datos)
    assert cargar_resultados(ruta) == datos


def test_reanudar_no_duplicar_ni_llamar_gemini(tmp_path, monkeypatch):
    from src import ensayo_bloque16
    ruta = tmp_path / "resultados.json"
    consulta, referencia = ensayo_bloque16.CASOS[0]
    datos = [{"consulta": consulta, "referencia": referencia, "respuesta": "Respuesta real previa", "precision": .2, "cobertura": .3, "f1": .24}]
    guardar_resultados(ruta, datos)
    def no_llamar(_):
        raise AssertionError("No debería llamar la API")
    monkeypatch.setattr(ensayo_bloque16, "consultar_modelo", no_llamar)
    assert ejecutar(1, ruta) == datos
