"""Pruebas offline del Bloque 22: no invocan Gemini ni consumen tokens."""

from typing import Any, List

import pytest
from pydantic import Field, ValidationError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, messages_from_dict, messages_to_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from src.agente_bloque22 import (
    RESPUESTA_VACIA,
    AlmacenSesiones,
    HERRAMIENTAS_BLOQUE22,
    construir_agente_con_memoria,
    construir_ejecutor,
    construir_prompt,
    diagnosticar_error_python_detallado,
    normalizar_resultado_agente,
    texto_salida,
)
from src.agente_con_herramientas import extraer_traza


# Formato real observado en Gemini: lista de bloques, no un str.
def bloques_gemini(texto: str) -> list:
    return [{
        "type": "text",
        "text": texto,
        "index": 0,
        "extras": {"signature": "firma_simulada"},
    }]


def config_sesion(session_id: str) -> dict:
    return {"configurable": {"session_id": session_id}}


def assert_historial_valido(historial) -> None:
    """Cada elemento es un mensaje con contenido str y es serializable."""
    mensajes = historial.messages
    assert all(isinstance(m, BaseMessage) for m in mensajes)
    assert all(isinstance(m.content, str) for m in mensajes)
    assert [type(m) for m in mensajes] == [HumanMessage, AIMessage] * (len(mensajes) // 2)
    assert messages_from_dict(messages_to_dict(mensajes)) == mensajes


# ---------------------------------------------------------------- herramientas

def test_dos_herramientas_diferenciadas():
    assert [x.name for x in HERRAMIENTAS_BLOQUE22] == [
        "diagnosticar_error_python_detallado", "sugerir_comando_git"
    ]


def test_esquema_documenta_tres_campos():
    esquema = diagnosticar_error_python_detallado.args_schema.model_json_schema()
    assert set(esquema["properties"]) == {"error", "contexto", "incluir_pasos"}
    assert all(esquema["properties"][key].get("description") for key in esquema["properties"])
    assert esquema["required"] == ["error"]


def test_herramienta_utiliza_parametro_opcional():
    simple = diagnosticar_error_python_detallado.invoke({"error": "ModuleNotFoundError"})
    detallado = diagnosticar_error_python_detallado.invoke({
        "error": "ModuleNotFoundError", "contexto": "al importar dotenv", "incluir_pasos": True
    })
    assert "Comprobaciones sugeridas" not in simple
    assert "Contexto aportado" not in simple
    assert "Comprobaciones sugeridas" in detallado
    assert "al importar dotenv" in detallado


def test_herramienta_valida_booleano_invalido():
    with pytest.raises(ValidationError):
        diagnosticar_error_python_detallado.invoke({
            "error": "NameError", "incluir_pasos": "talvez"
        })


def test_herramienta_rechaza_error_vacio():
    with pytest.raises(ValidationError):
        diagnosticar_error_python_detallado.invoke({"error": ""})


def test_herramienta_rechaza_error_solo_espacios():
    with pytest.raises(ValidationError):
        diagnosticar_error_python_detallado.invoke({"error": "   "})


def test_herramienta_rechaza_falta_de_error():
    with pytest.raises(ValidationError):
        diagnosticar_error_python_detallado.invoke({"incluir_pasos": True})


# ---------------------------------------------------------------- prompt

def test_prompt_incluye_historial_en_orden():
    prompt = construir_prompt()
    assert prompt.messages[1].variable_name == "chat_history"
    assert prompt.messages[-1].variable_name == "agent_scratchpad"


# ---------------------------------------------------------------- normalización

def test_texto_salida_gemini():
    assert texto_salida([{"type": "text", "text": "Hola"}, {"type": "text", "text": "Mundo"}]) == "Hola\nMundo"


def test_texto_salida_str_none_y_bloques_no_textuales():
    assert texto_salida("hola") == "hola"
    assert texto_salida(None) == ""
    assert texto_salida([]) == ""
    contenido = [{"type": "thinking", "thinking": "interno"}] + bloques_gemini("visible")
    assert texto_salida(contenido) == "visible"


def test_normalizar_convierte_bloques_y_conserva_traza():
    pasos = [("accion", "observacion")]
    original = {"entrada": "x", "output": bloques_gemini("Respuesta"), "intermediate_steps": pasos}
    normalizado = normalizar_resultado_agente(original)
    assert normalizado["output"] == "Respuesta"
    assert normalizado["intermediate_steps"] is pasos
    assert normalizado["entrada"] == "x"
    assert isinstance(original["output"], list)  # no muta la entrada


@pytest.mark.parametrize("salida", ["", "   ", [], None, [{"type": "text", "text": ""}]])
def test_normalizar_respuesta_vacia(salida):
    assert normalizar_resultado_agente({"output": salida})["output"] == RESPUESTA_VACIA


def test_normalizar_rechaza_resultado_no_dict():
    with pytest.raises(TypeError):
        normalizar_resultado_agente("texto suelto")


# ---------------------------------------------------------------- memoria

def agente_falso(entrada):
    historial = entrada["chat_history"]
    ultimo = historial[-2].content if len(historial) >= 2 else "sin antecedentes"
    return {"output": f"Historial previo: {len(historial)}; inicio: {ultimo}"}


def test_memoria_mismo_session_id_continua_conversacion():
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(RunnableLambda(agente_falso), almacen)
    config = config_sesion("a")
    primera = agente.invoke({"entrada": "mi error inicial"}, config=config)
    assert "0" in primera["output"]
    assert len(almacen.obtener_historial("a").messages) == 2
    segunda = agente.invoke({"entrada": "¿y ese error?"}, config=config)
    assert "Historial previo: 2" in segunda["output"]
    assert "mi error inicial" in segunda["output"]
    assert len(almacen.obtener_historial("a").messages) == 4


def test_memoria_no_filtra_sesiones():
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(RunnableLambda(agente_falso), almacen)
    agente.invoke({"entrada": "secreto de A"}, config=config_sesion("a"))
    otra = agente.invoke({"entrada": "¿qué dije?"}, config=config_sesion("b"))
    assert "Historial previo: 0" in otra["output"]
    assert "secreto de A" not in otra["output"]
    assert len(almacen.obtener_historial("a").messages) == 2
    assert len(almacen.obtener_historial("b").messages) == 2


def test_memoria_requiere_identificador_de_sesion():
    agente = construir_agente_con_memoria(RunnableLambda(agente_falso), AlmacenSesiones())
    with pytest.raises(ValueError):
        agente.invoke({"entrada": "hola"})


@pytest.mark.parametrize("session_id", ["", "   "])
def test_memoria_rechaza_session_id_vacio(session_id):
    agente = construir_agente_con_memoria(RunnableLambda(agente_falso), AlmacenSesiones())
    with pytest.raises(ValueError):
        agente.invoke({"entrada": "hola"}, config=config_sesion(session_id))


def test_cerrar_sesion_limpia_historial():
    almacen = AlmacenSesiones()
    almacen.obtener_historial("a").add_user_message("hola")
    almacen.cerrar_sesion("a")
    assert len(almacen.obtener_historial("a").messages) == 0


def test_cerrar_sesion_reinicia_contexto_del_agente():
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(RunnableLambda(agente_falso), almacen)
    agente.invoke({"entrada": "dato previo"}, config=config_sesion("a"))
    almacen.cerrar_sesion("a")
    almacen.cerrar_sesion("inexistente")  # no debe fallar
    nueva = agente.invoke({"entrada": "¿recuerdas?"}, config=config_sesion("a"))
    assert "Historial previo: 0" in nueva["output"]


def test_memoria_con_respuesta_vacia_guarda_mensaje_valido():
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(
        RunnableLambda(lambda _: {"output": [], "intermediate_steps": []}), almacen
    )
    resultado = agente.invoke({"entrada": "hola"}, config=config_sesion("a"))
    assert resultado["output"] == RESPUESTA_VACIA
    historial = almacen.obtener_historial("a")
    assert historial.messages[-1].content == RESPUESTA_VACIA
    assert_historial_valido(historial)


# ---------------------------------------------------------------- regresión Gemini

def test_regresion_salida_estructurada_gemini_dos_turnos():
    """Reproduce el fallo real: output como lista de bloques de Gemini.

    El agente falso formatea el prompt real, que es donde MessagesPlaceholder
    convierte chat_history en mensajes y donde antes ocurría
    MESSAGE_COERCION_FAILURE en el segundo turno.
    """
    prompt = construir_prompt()
    historiales_recibidos: List[list] = []
    paso = ("accion_simulada", "observacion_simulada")

    def agente_gemini_falso(entrada):
        prompt.invoke({
            "entrada": entrada["entrada"],
            "chat_history": entrada["chat_history"],
            "agent_scratchpad": [],
        })
        historiales_recibidos.append(list(entrada["chat_history"]))
        return {
            "output": bloques_gemini("La solución es instalar python-dotenv."),
            "intermediate_steps": [paso],
        }

    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(RunnableLambda(agente_gemini_falso), almacen)
    config = config_sesion("dev")

    # 1. Primer turno
    primera = agente.invoke({"entrada": "Tengo ModuleNotFoundError con dotenv"}, config=config)
    assert primera["output"] == "La solución es instalar python-dotenv."
    assert primera["intermediate_steps"] == [paso]
    # 2. Historial con mensajes válidos
    historial = almacen.obtener_historial("dev")
    assert len(historial.messages) == 2
    assert_historial_valido(historial)

    # 3/4. Segundo turno: recibe contexto y no hay MESSAGE_COERCION_FAILURE
    segunda = agente.invoke({"entrada": "¿Y para ese mismo error?"}, config=config)
    contexto = historiales_recibidos[1]
    assert [m.content for m in contexto] == [
        "Tengo ModuleNotFoundError con dotenv",
        "La solución es instalar python-dotenv.",
    ]
    # 5. Respuesta final utilizable  6. Traza disponible
    assert isinstance(segunda["output"], str) and segunda["output"]
    assert segunda["intermediate_steps"] == [paso]
    assert len(historial.messages) == 4
    assert_historial_valido(historial)


# ---------------------------------------------------------------- integración con AgentExecutor

class ModeloGeminiFalso(BaseChatModel):
    """Modelo de chat sin red que devuelve respuestas predefinidas.

    Permite ejercitar create_tool_calling_agent + AgentExecutor reales.
    """

    respuestas: List[AIMessage]
    recibidos: List[List[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "gemini-falso"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ModeloGeminiFalso":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.recibidos.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.respuestas.pop(0))])


def test_agent_executor_real_con_salida_gemini_y_herramienta():
    modelo = ModeloGeminiFalso(respuestas=[
        AIMessage(content="", tool_calls=[{
            "name": "diagnosticar_error_python_detallado",
            "args": {"error": "ModuleNotFoundError", "contexto": "al importar dotenv",
                     "incluir_pasos": True},
            "id": "llamada_1",
        }]),
        AIMessage(content=bloques_gemini("Instala python-dotenv en el entorno virtual.")),
        AIMessage(content=bloques_gemini("Revisa 'python -m pip show python-dotenv'.")),
    ])
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(construir_ejecutor(modelo), almacen)
    config = config_sesion("dev")

    primera = agente.invoke({"entrada": "Tengo ModuleNotFoundError al importar dotenv"}, config=config)
    assert primera["output"] == "Instala python-dotenv en el entorno virtual."
    traza = extraer_traza(primera)
    assert [e["herramienta"] for e in traza] == ["diagnosticar_error_python_detallado"]
    assert traza[0]["argumentos"]["incluir_pasos"] is True
    assert "Comprobaciones sugeridas" in traza[0]["observacion"]
    assert_historial_valido(almacen.obtener_historial("dev"))

    segunda = agente.invoke({"entrada": "¿Qué pasos reviso para ese error?"}, config=config)
    assert segunda["output"] == "Revisa 'python -m pip show python-dotenv'."
    assert extraer_traza(segunda) == []
    # El modelo recibió en el segundo turno: system + 2 de historial + humano.
    contenidos = [m.content for m in modelo.recibidos[-1]]
    assert contenidos[1:] == [
        "Tengo ModuleNotFoundError al importar dotenv",
        "Instala python-dotenv en el entorno virtual.",
        "¿Qué pasos reviso para ese error?",
    ]
    assert len(almacen.obtener_historial("dev").messages) == 4
    assert_historial_valido(almacen.obtener_historial("dev"))
