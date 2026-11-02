"""Bloque 14: pruebas del cliente Gemini sin llamadas reales a la API.

Ejecutar desde la raíz: python -m pytest tests/ -v
"""
from unittest.mock import Mock, patch

import pytest
import src.cliente as cliente

URL = "https://example.invalid/gemini"


@pytest.fixture(autouse=True)
def reiniciar_costo_total():
    """Aísla el estado global entre pruebas."""
    cliente.costo_total_sesion = 0.0
    yield
    cliente.costo_total_sesion = 0.0


@pytest.mark.parametrize("codigo", [401, 403])
def test_enviar_peticion_credencial_invalida(codigo):
    with patch("src.cliente.requests.post", return_value=Mock(status_code=codigo)) as post:
        with pytest.raises(ValueError, match="Credencial inválida"):
            cliente.enviar_peticion(URL, {}, {})
    post.assert_called_once()


@pytest.mark.parametrize("codigo", [429, 500, 502, 503])
def test_enviar_peticion_error_transitorio(codigo):
    with patch("src.cliente.requests.post", return_value=Mock(status_code=codigo)):
        with pytest.raises(TimeoutError, match="error temporal|cuota excedida"):
            cliente.enviar_peticion(URL, {}, {})


def test_enviar_peticion_exito():
    respuesta = Mock(status_code=200)
    respuesta.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hola"}]}}]}
    with patch("src.cliente.requests.post", return_value=respuesta) as post:
        assert cliente.enviar_peticion(URL, {"x-goog-api-key": "falsa"}, {"contents": []}) == respuesta.json.return_value
    post.assert_called_once()
    assert post.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize("excepcion", [
    __import__("requests").exceptions.Timeout("timeout simulado"),
    __import__("requests").exceptions.ConnectionError("red simulada"),
])
def test_enviar_peticion_problema_red(excepcion):
    with patch("src.cliente.requests.post", side_effect=excepcion):
        with pytest.raises(TimeoutError):
            cliente.enviar_peticion(URL, {}, {})


def test_con_reintento_se_recupera_y_espera_con_backoff():
    tarea = Mock(side_effect=[TimeoutError("temporal"), TimeoutError("temporal"), "ok"])
    with patch("src.cliente.time.sleep") as sleep, patch("src.cliente.random.uniform", return_value=0):
        assert cliente.con_reintento(tarea, intentos=3) == "ok"
    assert tarea.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [2, 4]


def test_con_reintento_no_reintenta_credencial():
    tarea = Mock(side_effect=ValueError("credencial inválida"))
    with patch("src.cliente.time.sleep") as sleep:
        with pytest.raises(ValueError, match="credencial inválida"):
            cliente.con_reintento(tarea)
    assert tarea.call_count == 1
    sleep.assert_not_called()


def test_con_reintento_propaga_timeout_tras_agotar():
    error_original = TimeoutError("fallo persistente")
    tarea = Mock(side_effect=error_original)
    with patch("src.cliente.time.sleep") as sleep:
        with pytest.raises(TimeoutError) as error:
            cliente.con_reintento(tarea, intentos=3)
    assert error.value is error_original
    assert tarea.call_count == 3
    assert sleep.call_count == 2


def test_registrar_costo_calcula_y_acumula():
    respuesta = {"usageMetadata": {"totalTokenCount": 1000}}
    assert cliente.registrar_costo(respuesta) == pytest.approx(cliente.COSTO_POR_1000_TOKENS)
    assert cliente.registrar_costo(respuesta) == pytest.approx(cliente.COSTO_POR_1000_TOKENS)
    assert cliente.costo_total_sesion == pytest.approx(2 * cliente.COSTO_POR_1000_TOKENS)


def test_registrar_costo_sin_metadatos():
    assert cliente.registrar_costo({}) == 0.0
    assert cliente.costo_total_sesion == 0.0


def test_consultar_modelo_convierte_timeout_agotado():
    with patch("src.cliente.armar_peticion", return_value=(URL, {}, {})), patch(
        "src.cliente.con_reintento", side_effect=TimeoutError("se agotaron los intentos")
    ), patch("src.cliente.registrar_costo") as costo:
        with pytest.raises(RuntimeError, match="tras varios intentos"):
            cliente.consultar_modelo("Pregunta")
    costo.assert_not_called()


def test_consultar_modelo_propaga_error_de_credencial():
    with patch("src.cliente.armar_peticion", return_value=(URL, {}, {})), patch(
        "src.cliente.con_reintento", side_effect=ValueError("credencial inválida")
    ), patch("src.cliente.registrar_costo") as costo:
        with pytest.raises(ValueError, match="credencial inválida"):
            cliente.consultar_modelo("Pregunta")
    costo.assert_not_called()


def test_consultar_modelo_registra_costo_una_vez_y_retorna_texto():
    respuesta = {"usageMetadata": {"totalTokenCount": 42}, "candidates": [{"content": {"parts": [{"text": "Santiago"}]}}]}
    with patch("src.cliente.armar_peticion", return_value=(URL, {}, {})), patch(
        "src.cliente.con_reintento", return_value=respuesta
    ), patch("src.cliente.registrar_costo") as costo, patch(
        "src.cliente.extraer_texto", return_value="Santiago"
    ):
        assert cliente.consultar_modelo("¿Capital de Chile?") == "Santiago"
    costo.assert_called_once_with(respuesta)


def test_consultar_modelo_agrega_instruccion_de_sistema():
    cuerpo = {"contents": [{"parts": [{"text": "Hola"}]}]}
    with patch("src.cliente.armar_peticion", return_value=(URL, {}, cuerpo)), patch(
        "src.cliente.con_reintento", return_value={}
    ), patch("src.cliente.registrar_costo"), patch("src.cliente.extraer_texto", return_value="OK"):
        cliente.consultar_modelo("Hola", "Responde en JSON")
    assert cuerpo["systemInstruction"] == {"parts": [{"text": "Responde en JSON"}]}
