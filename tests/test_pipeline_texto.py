"""Pruebas unitarias del Bloque 15: python -m pytest tests/test_pipeline_texto.py -v"""
import pytest

from src.pipeline_texto import (
    limpiar_texto, tokenizar, procesar_texto, vectorizar, coincidencia_palabras,
)


def test_procesar_texto_normaliza_mayusculas_y_puntuacion():
    assert procesar_texto("El Cielo, es AZUL!") == ["el", "cielo", "es", "azul"]


def test_procesar_texto_solo_puntuacion_devuelve_lista_vacia():
    assert procesar_texto("¡¡¡...!!!") == []


def test_limpieza_conserva_tildes_y_numeros():
    assert limpiar_texto("  ¡Ñandú!  3  ") == "ñandú 3"


def test_limpieza_rechaza_otros_tipos():
    with pytest.raises(TypeError, match="espera str"):
        limpiar_texto(None)


def test_tokenizar_texto_vacio():
    assert tokenizar("") == []


def test_vectorizar_cuenta_repeticiones():
    assert vectorizar(["el", "gato", "el"])["el"] == 2


def test_comparacion_antes_y_despues():
    referencia, respuesta = "El cielo es azul.", "el cielo es azul"
    assert coincidencia_palabras(referencia, respuesta, normalizar=False) == 0.5
    assert coincidencia_palabras(referencia, respuesta, normalizar=True) == 1.0


def test_referencia_vacia_no_divide_por_cero():
    assert coincidencia_palabras("!!!", "hola") == 0.0


def test_orden_no_se_considera():
    assert coincidencia_palabras("El perro persiguió al gato.", "El gato persiguió al perro.") == 1.0
