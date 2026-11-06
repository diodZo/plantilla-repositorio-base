"""Bloque 21: agente educativo con dos herramientas y traza verificable.

Ejecutar desde la raíz: python -m src.agente_con_herramientas
No modifica el repositorio ni ejecuta comandos Git.
"""

import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent


@tool
def diagnosticar_error_python(error: str) -> str:
    """Orienta sobre errores de Python concretos (ModuleNotFoundError, NameError, TypeError).

    Usar cuando el usuario menciona un error de ejecución Python y necesita
    identificar su causa probable y comprobaciones seguras. No ejecuta código.
    """
    consulta = error.casefold().strip()
    if not consulta:
        return "Indica el nombre del error y el mensaje completo para orientar el diagnóstico."
    if "modulenotfounderror" in consulta:
        return ("ModuleNotFoundError: comprueba el nombre del módulo, el entorno virtual "
                "activo y la instalación con 'python -m pip show NOMBRE_PAQUETE'. "
                "El nombre de importación puede diferir del nombre del paquete.")
    if "nameerror" in consulta:
        return ("NameError: revisa el nombre de la variable, su definición previa "
                "y si está disponible en el ámbito donde se usa.")
    if "typeerror" in consulta:
        return ("TypeError: revisa el tipo de los valores y los argumentos que "
                "espera la función. Comparte el traceback para afinar el diagnóstico.")
    return "No hay una guía local para ese error; solicita el traceback completo."


@tool
def sugerir_comando_git(operacion: str) -> str:
    """Sugiere comandos Git de solo lectura para inspeccionar un repositorio.

    Usar cuando el usuario desea consultar estado, diferencias o historial de Git.
    Nunca ejecuta comandos, crea commits, modifica archivos ni publica cambios.
    """
    consulta = operacion.casefold().strip()
    if "estado" in consulta or "status" in consulta or "cambios pendientes" in consulta:
        return "Ejecuta 'git status --short' para ver cambios locales sin modificarlos."
    if "diferencia" in consulta or "diff" in consulta:
        return "Ejecuta 'git diff' para inspeccionar cambios no preparados."
    if "historial" in consulta or "log" in consulta or "commit" in consulta:
        return "Ejecuta 'git log -5 --oneline' para ver commits recientes."
    return "Indica si quieres consultar estado, diferencias o historial; no se ejecutó ningún comando."


HERRAMIENTAS = [diagnosticar_error_python, sugerir_comando_git]


def construir_ejecutor(modelo, *, verbose=False):
    """Inyecta modelo y construye un agente con traza de acciones observable."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente educativo para desarrolladores Python. "
         "Usa diagnosticar_error_python para errores de ejecución de Python, "
         "sugerir_comando_git para consultar comandos Git de inspección, "
         "y responde directamente a preguntas generales. "
         "No afirmes haber ejecutado comandos ni inspeccionado archivos. "
         "No inventes diagnósticos confirmados: entrega orientación general. "
         "Si una consulta necesita ambas herramientas, puedes usar las dos. "
         "Responde en español de manera clara."),
        ("human", "{entrada}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agente = create_tool_calling_agent(modelo, HERRAMIENTAS, prompt)
    return AgentExecutor(
        agent=agente,
        tools=HERRAMIENTAS,
        verbose=verbose,
        return_intermediate_steps=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )


def extraer_traza(resultado):
    """Devuelve una lista de eventos públicos herramienta/argumentos/observación.

    No intenta reconstruir razonamiento interno del modelo.
    """
    eventos = []
    for accion, observacion in resultado.get("intermediate_steps", []):
        eventos.append({
            "herramienta": accion.tool,
            "argumentos": accion.tool_input,
            "observacion": str(observacion),
        })
    return eventos


def main():
    load_dotenv()
    clave = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    if not clave:
        raise RuntimeError("Configura GOOGLE_API_KEY, GEMINI_API_KEY o API_KEY en .env")
    modelo = ChatGoogleGenerativeAI(
        model=os.getenv("AI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=clave,
    )
    ejecutor = construir_ejecutor(modelo, verbose=False)
    ejemplos = [
        ("Python", "Al ejecutar Python obtengo ModuleNotFoundError. ¿Qué reviso?", "diagnosticar_error_python"),
        ("Git", "¿Qué comando Git puedo usar para ver el estado de mi repositorio?", "sugerir_comando_git"),
        ("General", "¿Qué es una función en programación?", None),
    ]
    for nombre, entrada, esperado in ejemplos:
        print(f"\n--- {nombre} ---\nPregunta: {entrada}")
        resultado = ejecutor.invoke({"entrada": entrada})
        traza = extraer_traza(resultado)
        print("Herramientas utilizadas:", [e["herramienta"] for e in traza])
        print("Respuesta:", resultado["output"])
        if esperado is not None and esperado not in [e["herramienta"] for e in traza]:
            print(f"ADVERTENCIA: no se observó la herramienta esperada ({esperado}).")


if __name__ == "__main__":
    main()
