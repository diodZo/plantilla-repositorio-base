"""Bloque 22: herramienta Pydantic y agente con memoria en sesiones aisladas.

Desde la raíz del proyecto: python -m src.agente_bloque22
Las herramientas orientan; no ejecutan código Python ni comandos Git.
"""

import os
from typing import Any, Dict

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agente_con_herramientas import extraer_traza, sugerir_comando_git

RESPUESTA_VACIA = "El modelo no devolvió texto en esta respuesta."

class ArgumentosDiagnosticoPython(BaseModel):
    """Argumentos descritos y validados antes de invocar la herramienta."""

    # Elimina espacios antes de validar: un error "   " cuenta como vacío.
    model_config = ConfigDict(str_strip_whitespace=True)

    error: str = Field(
        min_length=1,
        description="Nombre o texto del error de Python, p. ej. ModuleNotFoundError o TypeError.",
    )
    contexto: str = Field(
        default="",
        description="Datos adicionales del traceback o del entorno, si el usuario los indicó.",
    )
    incluir_pasos: bool = Field(
        default=False,
        description="Si es True, incluir comprobaciones prácticas, además de la causa general.",
    )


@tool("diagnosticar_error_python_detallado", args_schema=ArgumentosDiagnosticoPython)
def diagnosticar_error_python_detallado(
    error: str, contexto: str = "", incluir_pasos: bool = False
) -> str:
    """Orienta sobre un error de ejecución Python; permite solicitar pasos y aportar contexto.

    Úsala cuando el usuario mencione ModuleNotFoundError, NameError o TypeError.
    No ejecuta scripts ni instala paquetes y no afirma haber comprobado un entorno.
    """
    nombre = error.casefold().strip()
    if "modulenotfounderror" in nombre:
        respuesta = "ModuleNotFoundError: Python no encuentra el módulo solicitado."
        pasos = "Revisa el import, el entorno virtual y 'python -m pip show PAQUETE'."
    elif "nameerror" in nombre:
        respuesta = "NameError: un nombre no está definido en el ámbito actual."
        pasos = "Revisa la definición previa, el ámbito y la escritura del nombre."
    elif "typeerror" in nombre:
        respuesta = "TypeError: una operación o llamada recibió tipos o argumentos incompatibles."
        pasos = "Comprueba tipos, parámetros y el traceback de la operación."
    else:
        respuesta = "No hay una guía local para ese error; solicita el traceback completo."
        pasos = "Verifica el mensaje exacto y el lugar donde aparece."
    if contexto.strip():
        respuesta += f" Contexto aportado por el usuario: {contexto.strip()}"
    if incluir_pasos:
        respuesta += f" Comprobaciones sugeridas: {pasos}"
    return respuesta


HERRAMIENTAS_BLOQUE22 = [diagnosticar_error_python_detallado, sugerir_comando_git]


def construir_prompt():
    """chat_history recuerda turnos anteriores; scratchpad es solo del turno actual."""
    return ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente educativo de desarrollo Python y Git. "
         "Usa diagnosticar_error_python_detallado para errores Python y "
         "sugerir_comando_git para comandos Git de consulta. "
         "Si el usuario se refiere a un mensaje anterior, utiliza chat_history. "
         "No inventes información de sesiones anteriores ni afirmes ejecutar comandos. "
         "Si no conoces el antecedente, solicítalo. Responde en español."),
        MessagesPlaceholder("chat_history"),
        ("human", "{entrada}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])


def construir_ejecutor(modelo, *, verbose=False):
    """Crea agente y conserva trazas de las herramientas invocadas."""
    agente = create_tool_calling_agent(modelo, HERRAMIENTAS_BLOQUE22, construir_prompt())
    return AgentExecutor(
        agent=agente,
        tools=HERRAMIENTAS_BLOQUE22,
        verbose=verbose,
        return_intermediate_steps=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )


class AlmacenSesiones:
    """Memoria efímera para el ejercicio: no persiste al reiniciar el programa."""

    def __init__(self):
        self.historiales: Dict[str, InMemoryChatMessageHistory] = {}

    def obtener_historial(self, session_id: str) -> InMemoryChatMessageHistory:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id debe ser un texto no vacío.")
        if session_id not in self.historiales:
            self.historiales[session_id] = InMemoryChatMessageHistory()
        return self.historiales[session_id]

    def cerrar_sesion(self, session_id: str) -> None:
        self.historiales.pop(session_id, None)


def texto_salida(contenido: Any) -> str:
    """Convierte el contenido de Gemini (str o lista de bloques) en texto plano.

    Gemini puede devolver ``[{"type": "text", "text": ..., "extras": {...}}]``.
    Solo se conservan los bloques de texto; los demás (p. ej. razonamiento
    o firmas) se descartan porque no forman parte de la respuesta visible.
    """
    if contenido is None:
        return ""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, (list, tuple)):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif (
                isinstance(bloque, dict)
                and bloque.get("type", "text") == "text"
                and isinstance(bloque.get("text"), str)
            ):
                partes.append(bloque["text"])
        return "\n".join(partes)
    return str(contenido)


def normalizar_resultado_agente(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Deja ``output`` como texto no vacío y conserva el resto de claves.

    Es necesario porque RunnableWithMessageHistory interpreta una lista en
    ``output`` como una lista de mensajes y guardaría los bloques de Gemini
    en el historial; en el turno siguiente fallaría la conversión a mensajes
    (MESSAGE_COERCION_FAILURE). ``intermediate_steps`` no se modifica.
    """
    if not isinstance(resultado, dict):
        raise TypeError(
            f"Se esperaba un dict del AgentExecutor; se recibió {type(resultado).__name__}."
        )
    texto = texto_salida(resultado.get("output")).strip()
    return {**resultado, "output": texto or RESPUESTA_VACIA}


def construir_agente_con_memoria(ejecutor_agente: Runnable, almacen: AlmacenSesiones):
    """Envuelve el ejecutor con memoria por session_id.

    La normalización ocurre dentro del runnable envuelto, antes de que
    RunnableWithMessageHistory lea ``output`` para guardarlo en el historial.
    """
    ejecutor_normalizado = ejecutor_agente | RunnableLambda(normalizar_resultado_agente)
    return RunnableWithMessageHistory(
        ejecutor_normalizado,
        almacen.obtener_historial,
        input_messages_key="entrada",
        history_messages_key="chat_history",
        output_messages_key="output",
    )


def main():
    load_dotenv()
    clave = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    if not clave:
        raise RuntimeError("Configura GOOGLE_API_KEY, GEMINI_API_KEY o API_KEY en .env")

    modelo = ChatGoogleGenerativeAI(
        model=os.getenv("AI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=clave,
    )
    almacen = AlmacenSesiones()
    agente = construir_agente_con_memoria(construir_ejecutor(modelo), almacen)
    ejemplos = [
        ("desarrollador_1", "Tengo un ModuleNotFoundError al importar dotenv. ¿Qué significa?"),
        ("desarrollador_1", "¿Y qué pasos debería revisar para ese mismo error?"),
        ("desarrollador_2", "¿Qué error de Python mencioné antes en esta conversación?"),
        ("desarrollador_2", "¿Qué comando Git muestra los cambios pendientes?"),
    ]
    for session_id, entrada in ejemplos:
        resultado = agente.invoke(
            {"entrada": entrada},
            config={"configurable": {"session_id": session_id}},
        )
        print(f"\nSesión: {session_id}\nPregunta: {entrada}")
        print("Herramientas:", [x["herramienta"] for x in extraer_traza(resultado)])
        print("Respuesta:", texto_salida(resultado["output"]))
        print("Mensajes en historial:", len(almacen.obtener_historial(session_id).messages))


if __name__ == "__main__":
    main()
