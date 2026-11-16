"""Bloque 28: medición de latencia por etapas (sin red)."""
import time

import pytest

from src.rag.medicion import Medidor


class RelojFalso:
    def __init__(self, *instantes):
        self.instantes = list(instantes)

    def __call__(self):
        return self.instantes.pop(0)


def test_etapas_y_total_independiente_con_reloj_falso():
    # total inicia en 0; etapa a: 1→3 (2 s); etapa b: 4→4.5 (0.5 s); total termina en 6.
    m = Medidor(RelojFalso(0.0, 1.0, 3.0, 4.0, 4.5, 6.0))
    with m.total():
        with m.etapa("a"):
            pass
        with m.etapa("b"):
            pass
    assert m.tiempos_ms == {"a": 2000.0, "b": 500.0}
    assert m.total_ms == 6000.0                  # medido, no sumado
    assert m.sobrecarga_ms == 3500.0             # tiempo fuera de las etapas


def test_etapa_fallida_registra_tiempo_y_propaga_la_excepcion():
    m = Medidor(RelojFalso(0.0, 1.0, 1.25, 2.0))
    with pytest.raises(ConnectionError, match="red"):
        with m.total():
            with m.etapa("generacion"):
                raise ConnectionError("red caída")
    assert m.tiempos_ms["generacion"] == 250.0
    assert m.etapas_fallidas == ["generacion"]
    assert m.total_ms == 2000.0


def test_validaciones_del_medidor():
    m = Medidor()
    with pytest.raises(ValueError):
        with m.etapa(""):
            pass
    with m.etapa("x"):
        pass
    with pytest.raises(ValueError, match="ya fue medida"):
        with m.etapa("x"):
            pass
    with m.total():
        pass
    with pytest.raises(ValueError, match="una vez"):
        with m.total():
            pass


def test_como_dict_marca_etapas_no_ejecutadas_como_none():
    m = Medidor(RelojFalso(0.0, 0.0015, 0.002, 0.004))
    with m.total():
        with m.etapa("embed_query"):
            pass
    datos = m.como_dict(("validacion_indice", "embed_query", "generacion"))
    assert datos["tiempos_ms"] == {"validacion_indice": None, "embed_query": 0.5, "generacion": None}
    assert datos["tiempo_total_ms"] == 4.0
    assert datos["sobrecarga_ms"] == 3.5
    assert Medidor().sobrecarga_ms is None


def test_precision_basica_de_perf_counter():
    m = Medidor()
    with m.total():
        with m.etapa("espera"):
            time.sleep(0.02)
    assert 15.0 <= m.tiempos_ms["espera"] < 1000.0
    assert m.total_ms >= m.tiempos_ms["espera"]
    assert m.sobrecarga_ms >= 0.0
