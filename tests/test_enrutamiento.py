"""Pruebas offline del Bloque 19: no requieren API ni consumen tokens."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from src.enrutamiento import (
    construir_cadena_con_enrutamiento,
    construir_paso_clasificacion,
)


def _probar_ruta(categoria, destino):
    clasificador = MagicMock(return_value=categoria)
    rutas = {nombre: MagicMock(return_value=f"respuesta de {nombre}")
             for nombre in ("pregunta", "queja", "sugerencia")}
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=clasificador,
        cadena_pregunta=rutas["pregunta"],
        cadena_queja=rutas["queja"],
        cadena_sugerencia=rutas["sugerencia"],
    )
    resultado = cadena.invoke({"mensaje": "Mensaje de ejemplo"})
    assert resultado == f"respuesta de {destino}"
    clasificador.assert_called_once()
    for nombre, ruta in rutas.items():
        assert ruta.call_count == (1 if nombre == destino else 0)
    assert rutas[destino].call_args.args[0]["mensaje"] == "Mensaje de ejemplo"
    assert rutas[destino].call_args.args[0]["categoria"] == categoria


def test_enrutamiento_queja():
    _probar_ruta("queja", "queja")


def test_enrutamiento_sugerencia():
    _probar_ruta("sugerencia", "sugerencia")


def test_enrutamiento_pregunta():
    _probar_ruta("pregunta", "pregunta")


def test_enrutamiento_categoria_desconocida_usa_default():
    _probar_ruta("categoria_inventada", "pregunta")


def test_clasificacion_normaliza_mayusculas_y_espacios():
    modelo_falso = MagicMock(return_value=AIMessage(content="Queja \n"))
    clasificacion = construir_paso_clasificacion(modelo_falso)
    resultado = clasificacion.invoke({"mensaje": "La aplicación falla"})
    assert resultado == "queja"
    modelo_falso.assert_called_once()
