"""Pruebas sin red del Bloque 18."""
import pytest
from langchain_core.runnables import RunnableLambda
from src.cadena_tres_pasos import construir_cadena


def test_cadena_realiza_tres_pasos_y_produce_respuesta_final():
    llamadas = []
    respuestas = [
        "Categoría: dependencias. Problema: falta dotenv.",
        "Instala python-dotenv en el entorno virtual activo.",
        "Verifica que tu entorno esté activo y ejecuta pip install python-dotenv.",
    ]

    def modelo_falso(entrada):
        llamadas.append(entrada)
        return respuestas[len(llamadas) - 1]

    cadena = construir_cadena(RunnableLambda(modelo_falso))
    resultado = cadena.invoke({"consulta": "No se encuentra dotenv"})

    assert len(llamadas) == 3
    assert resultado == respuestas[-1]
    assert "falta dotenv" in llamadas[1].to_string()
    assert "Instala python-dotenv" in llamadas[2].to_string()


def test_falta_variable_consulta():
    cadena = construir_cadena(RunnableLambda(lambda _: "respuesta"))
    with pytest.raises(KeyError):
        cadena.invoke({"otra_clave": "texto"})


def test_reutilizacion_de_cadena():
    numero = 0
    def modelo_falso(_):
        nonlocal numero
        numero += 1
        return f"resultado {numero}"
    cadena = construir_cadena(RunnableLambda(modelo_falso))
    assert cadena.invoke({"consulta": "caso uno"}) == "resultado 3"
    assert cadena.invoke({"consulta": "caso dos"}) == "resultado 6"
