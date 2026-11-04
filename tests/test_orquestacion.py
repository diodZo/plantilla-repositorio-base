"""Bloque 20: pruebas offline de fallback, clasificación y protección global."""

import logging
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.enrutamiento import (
    construir_cadena_con_enrutamiento,
    construir_cadena_queja_segura,
    construir_paso_clasificacion,
    procesar_mensaje_seguro,
)


def _fallar(_entrada):
    raise ConnectionError("fallo simulado de la red")


def test_cadena_queja_usa_fallback_ante_fallo_del_modelo():
    cadena_queja_rota = RunnableLambda(_fallar)
    cadena_segura = construir_cadena_queja_segura(cadena_queja_rota)
    resultado = cadena_segura.invoke({"mensaje": "La aplicación no funciona"})
    assert "equipo de soporte" in resultado.lower()


def test_cadena_queja_no_usa_fallback_si_funciona():
    cadena_queja = RunnableLambda(lambda _entrada: "queja resuelta normalmente")
    cadena_segura = construir_cadena_queja_segura(cadena_queja)
    assert cadena_segura.invoke({"mensaje": "Problema"}) == "queja resuelta normalmente"


def test_fallo_en_clasificacion_devuelve_respuesta_segura(caplog):
    clasificador_roto = MagicMock(side_effect=ConnectionError("fallo simulado"))
    cadena = construir_cadena_con_enrutamiento(paso_clasificacion=clasificador_roto)
    with caplog.at_level(logging.ERROR):
        resultado = procesar_mensaje_seguro(cadena, "No puedo ingresar")
    assert "no pudimos procesar" in resultado.lower()
    assert "error al procesar" in caplog.text.lower()


def test_fallo_de_ruta_no_protegida_devuelve_respuesta_segura():
    clasificador = MagicMock(return_value="pregunta")
    ruta_pregunta_rota = RunnableLambda(_fallar)
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=clasificador,
        cadena_pregunta=ruta_pregunta_rota,
    )
    assert "no pudimos procesar" in procesar_mensaje_seguro(cadena, "Pregunta").lower()


def test_flujo_con_fallback_recupera_queja_sin_lanzar_excepcion():
    clasificador = MagicMock(return_value="queja")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=clasificador,
        cadena_queja=construir_cadena_queja_segura(RunnableLambda(_fallar)),
    )
    assert "equipo de soporte" in procesar_mensaje_seguro(cadena, "Se cae").lower()


def test_clasificacion_sigue_normalizando():
    modelo_falso = MagicMock(return_value=AIMessage(content="Queja \n"))
    assert construir_paso_clasificacion(modelo_falso).invoke({"mensaje": "Error"}) == "queja"


@pytest.mark.parametrize("categoria", ["queja", "sugerencia", "pregunta", "desconocida"])
def test_rutas_sin_fallo_mantienen_comportamiento(categoria):
    clasificador = MagicMock(return_value=categoria)
    rutas = {nombre: MagicMock(return_value=f"OK {nombre}") for nombre in ("pregunta", "queja", "sugerencia")}
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=clasificador,
        cadena_queja=rutas["queja"],
        cadena_sugerencia=rutas["sugerencia"],
        cadena_pregunta=rutas["pregunta"],
    )
    esperado = categoria if categoria in rutas else "pregunta"
    assert procesar_mensaje_seguro(cadena, "mensaje") == f"OK {esperado}"
    for nombre, ruta in rutas.items():
        assert ruta.call_count == int(nombre == esperado)
