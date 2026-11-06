"""Pruebas offline de herramientas y lectura de trazas del Bloque 21."""
from types import SimpleNamespace
from src.agente_con_herramientas import (
    HERRAMIENTAS, diagnosticar_error_python, sugerir_comando_git, extraer_traza
)


def test_hay_dos_herramientas_diferenciadas():
    assert [h.name for h in HERRAMIENTAS] == [
        "diagnosticar_error_python", "sugerir_comando_git"
    ]
    assert all(h.description for h in HERRAMIENTAS)


def test_herramienta_python_orienta_sin_ejecutar_codigo():
    texto = diagnosticar_error_python.invoke({"error": "ModuleNotFoundError: No module named dotenv"})
    assert "entorno virtual" in texto


def test_herramienta_python_error_desconocido():
    assert "guía local" in diagnosticar_error_python.invoke({"error": "OtroError"})


def test_herramienta_git_devuelve_comando_consulta():
    assert "git status --short" in sugerir_comando_git.invoke({"operacion": "ver estado"})


def test_herramienta_git_no_ejecuta_escrituras():
    texto = sugerir_comando_git.invoke({"operacion": "publicar"})
    assert "no se ejecutó" in texto


def test_extraer_traza_de_accion_y_observacion():
    accion = SimpleNamespace(tool="sugerir_comando_git", tool_input={"operacion": "estado"})
    pasos = [(accion, "git status --short")]
    resultado = extraer_traza({"intermediate_steps": pasos})
    assert resultado == [{
        "herramienta": "sugerir_comando_git",
        "argumentos": {"operacion": "estado"},
        "observacion": "git status --short",
    }]


def test_extraer_traza_sin_herramientas():
    assert extraer_traza({"intermediate_steps": []}) == []
