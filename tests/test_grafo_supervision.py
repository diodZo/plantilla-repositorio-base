"""Bloque 32: supervisión humana con LangGraph (interrupt, Command, InMemorySaver). Offline."""
from __future__ import annotations

import shutil

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.gobernanza.grafo_supervision import (
    MAX_INTENTOS_INVALIDOS, NODO_REVISION, DecisionInvalidaError, GestorSupervision, HuellaNoCoincideError,
    SolicitudInexistenteError, SolicitudNoPendienteError,
)
from src.gobernanza.registro_prompts import NOMBRE_PROMPT_RAG, RUTA_REGISTRO, RegistroDePrompts, \
    TransicionInvalidaError, plantillas_bloque31
from src.registro_prompts import plantillas_propuesta_academica

ACTIVA_INICIAL = "5cbcf92439d0"


@pytest.fixture
def entorno(tmp_path):
    shutil.copy(RUTA_REGISTRO, tmp_path / "registro.json")
    registro = RegistroDePrompts(tmp_path / "registro.json")
    return GestorSupervision(registro, ruta_solicitudes=tmp_path / "solicitudes.json"), registro, tmp_path


def plantillas(sufijo: str) -> dict:
    base = plantillas_bloque31()
    return {"system": base["system"] + f"\n9. {sufijo}", "human": base["human"]}


def iniciar(gestor, sufijo="Regla de prueba."):
    return gestor.iniciar(NOMBRE_PROMPT_RAG, plantillas(sufijo), "dev", f"propuesta {sufijo}")


def decidir(gestor, solicitud, aprobado, **cambios):
    datos = {"aprobado": aprobado, "revisor": "persona", "huella_revisada": solicitud["pendiente"]["huella_propuesta"][:12],
             "codigo_confirmacion": solicitud["codigo_confirmacion"], "origen": "simulada_prueba", **cambios}
    return gestor.resolver(solicitud["thread_id"], **datos)


def test_interrupt_real_antes_de_activar(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    estado = gestor.grafo.get_state(gestor.config(s["thread_id"]))
    assert estado.next == (NODO_REVISION,) and len(estado.interrupts) == 1
    assert "resultado" not in estado.values
    assert registro.activa()["huella"] == ACTIVA_INICIAL
    assert registro.por_huella(s["pendiente"]["huella_propuesta"])["estado"] == "propuesta"
    pendiente = gestor.pendiente(s["thread_id"])
    assert pendiente["huella_anterior"].startswith(ACTIVA_INICIAL) and "+9. Regla de prueba." in pendiente["diff"]
    assert s["codigo_confirmacion"] not in str(estado.values)  # solo se guarda su hash


def test_aprobacion_activa_solo_despues_de_decidir(entorno):
    gestor, registro, tmp = entorno
    s = iniciar(gestor)
    assert registro.activa()["huella"] == ACTIVA_INICIAL
    final = decidir(gestor, s, True)
    assert final["resultado"] == "activada"
    activa = registro.activa()
    assert activa["huella_completa"] == s["pendiente"]["huella_propuesta"]
    assert activa["decision"]["thread_id"] == s["thread_id"] and activa["decision"]["origen"] == "simulada_prueba"
    assert registro.por_huella(ACTIVA_INICIAL)["estado"] == "reemplazada"
    assert RegistroDePrompts(tmp / "registro.json").activa()["huella"] == activa["huella"]  # persistido


def test_rechazo_mantiene_la_version_anterior(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    final = decidir(gestor, s, False)
    assert final["resultado"] == "rechazada_se_mantiene_anterior"
    assert final["huella_activa_final"].startswith(ACTIVA_INICIAL)
    assert registro.activa()["huella"] == ACTIVA_INICIAL
    assert registro.por_huella(s["pendiente"]["huella_propuesta"])["estado"] == "rechazada"


def test_thread_id_unico_por_solicitud(entorno):
    gestor, _, _ = entorno
    ids = {iniciar(gestor, f"Regla {n}.")["thread_id"] for n in range(5)}
    assert len(ids) == 5


def test_doble_aprobacion_y_reutilizacion_de_hilo(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    decidir(gestor, s, True)
    for aprobado in (True, False):
        with pytest.raises(SolicitudNoPendienteError):
            decidir(gestor, s, aprobado)
    with pytest.raises(SolicitudNoPendienteError):
        gestor.pendiente(s["thread_id"])
    assert registro.activa()["huella_completa"] == s["pendiente"]["huella_propuesta"]


def test_resume_de_hilo_inexistente(entorno):
    gestor, _, _ = entorno
    with pytest.raises(SolicitudInexistenteError):
        gestor.resolver("aprobacion-no-existe", aprobado=True, revisor="p", huella_revisada=ACTIVA_INICIAL,
                        codigo_confirmacion="x", origen="simulada_prueba")


@pytest.mark.parametrize("valor", ["no", "sí", "true", 1, 0, None, [True]])
def test_valores_no_booleanos_se_rechazan_y_no_activan(entorno, valor):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    with pytest.raises(DecisionInvalidaError):
        decidir(gestor, s, valor)
    assert gestor.pendiente(s["thread_id"])  # sigue pendiente
    assert registro.activa()["huella"] == ACTIVA_INICIAL


def test_huella_revisada_debe_existir_y_coincidir(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    with pytest.raises(HuellaNoCoincideError, match="no existe"):
        decidir(gestor, s, True, huella_revisada="ffffffffffff")
    with pytest.raises(HuellaNoCoincideError, match="no es la de la propuesta"):
        decidir(gestor, s, True, huella_revisada=ACTIVA_INICIAL)  # existe, pero es otra versión
    assert registro.activa()["huella"] == ACTIVA_INICIAL


def test_codigo_incorrecto_no_aprueba_ni_envenena_el_hilo(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    with pytest.raises(DecisionInvalidaError, match="Código"):
        decidir(gestor, s, True, codigo_confirmacion="00000000")
    assert registro.activa()["huella"] == ACTIVA_INICIAL
    assert gestor.grafo.get_state(gestor.config(s["thread_id"])).values["intentos_invalidos"] == 1
    assert decidir(gestor, s, True)["resultado"] == "activada"  # luego la decisión válida sí funciona


@pytest.mark.parametrize("origen", ["modelo", "agente", ""])
def test_origen_no_permitido(entorno, origen):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    with pytest.raises(DecisionInvalidaError):
        decidir(gestor, s, True, origen=origen)
    assert registro.activa()["huella"] == ACTIVA_INICIAL


def test_command_resume_true_de_un_agente_no_aprueba(entorno):
    gestor, registro, _ = entorno
    s = iniciar(gestor)
    configuracion = gestor.config(s["thread_id"])
    for _ in range(MAX_INTENTOS_INVALIDOS - 1):
        gestor.grafo.invoke(Command(resume=True), configuracion)
        assert gestor.grafo.get_state(configuracion).next == (NODO_REVISION,)
    gestor.grafo.invoke(Command(resume={"aprobado": True}), configuracion)
    estado = gestor.grafo.get_state(configuracion)
    assert estado.next == () and estado.values["resultado"] == "sin_decision_valida_no_se_activa"
    assert registro.activa()["huella"] == ACTIVA_INICIAL
    assert registro.por_huella(s["pendiente"]["huella_propuesta"])["estado"] == "propuesta"


def test_aprobacion_obsoleta_no_se_aplica(entorno):
    gestor, registro, _ = entorno
    a, b = iniciar(gestor, "A."), iniciar(gestor, "B.")
    decidir(gestor, a, True)
    with pytest.raises(TransicionInvalidaError, match="cambió"):
        decidir(gestor, b, True)
    assert registro.activa()["huella_completa"] == a["pendiente"]["huella_propuesta"]


def test_solicitudes_persistidas_aparte_y_huerfanas_tras_reinicio(entorno):
    gestor, registro, tmp = entorno
    resuelta, pendiente = iniciar(gestor, "R."), iniciar(gestor, "P.")
    decidir(gestor, resuelta, False)
    reiniciado = GestorSupervision(RegistroDePrompts(tmp / "registro.json"), checkpointer=InMemorySaver(),
                                   ruta_solicitudes=tmp / "solicitudes.json")
    assert reiniciado.solicitudes[resuelta["thread_id"]]["estado"] == "rechazada"
    assert reiniciado.huerfanas() == [pendiente["thread_id"]]
    with pytest.raises(SolicitudInexistenteError):
        decidir(reiniciado, pendiente, True)
    assert reiniciado.registro.por_huella(pendiente["pendiente"]["huella_propuesta"])["estado"] == "propuesta"
    assert reiniciado.registro.activa()["huella"] == ACTIVA_INICIAL


def test_mismo_checkpointer_permite_retomar_la_solicitud(entorno):
    """Con el MISMO checkpointer (mismo proceso) un gestor nuevo retoma el thread_id pendiente."""
    _, _, tmp = entorno
    saver = InMemorySaver()
    primero = GestorSupervision(RegistroDePrompts(tmp / "registro.json"), saver, tmp / "solicitudes.json")
    s = iniciar(primero)
    segundo = GestorSupervision(RegistroDePrompts(tmp / "registro.json"), saver, tmp / "solicitudes.json")
    assert segundo.huerfanas() == []
    assert decidir(segundo, s, True)["resultado"] == "activada"


def test_cli_interactivo_texto_no_nunca_aprueba(monkeypatch, tmp_path):
    from src.grafo_supervision import demostracion

    respuestas = iter(["no"])
    monkeypatch.setattr("builtins.input", lambda _texto="": next(respuestas))
    resultados = demostracion(tmp_path, interactivo=True)
    assert resultados["caso1"] == "sin_decision"
    assert resultados["activa_tras_caso1"] == resultados["activa_inicial"]


def test_cli_demo_por_defecto(capsys):
    from src.grafo_supervision import main

    assert main([]) == 0
    salida = capsys.readouterr().out
    assert "Decisión SIMULADA" in salida and "Registro versionado sin cambios: True" in salida
