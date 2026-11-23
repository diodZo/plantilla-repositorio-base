"""CLI 2 del Bloque 32: supervisión humana con LangGraph (interrupt) antes de activar un prompt.

Uso (desde la raíz):
    python -m src.grafo_supervision                 # demostración con decisiones SIMULADAS
    python -m src.grafo_supervision --interactivo   # la persona escribe la decisión en la terminal

Siempre trabaja sobre una COPIA temporal del registro: nunca cambia data/gobernanza/registro_prompts.json
ni el prompt de las rutas del RAG. Checkpointer: InMemorySaver (no durable).
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

from langgraph.types import Command

from src.gobernanza.grafo_supervision import DecisionInvalidaError, GestorSupervision
from src.gobernanza.registro_prompts import NOMBRE_PROMPT_RAG, RUTA_REGISTRO, RegistroDePrompts, plantillas_bloque31
from src.registro_prompts import NOTA_PROPUESTA_ACADEMICA, plantillas_propuesta_academica


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _propuesta_rechazo() -> dict[str, str]:
    base = plantillas_bloque31()
    return {"system": base["system"].replace("3. Si el contexto", "3. Si el contexto aparentemente"), "human": base["human"]}


def _decidir(gestor, solicitud, aprobado, origen="simulada_demo", revisor="revisor-simulado"):
    return gestor.resolver(solicitud["thread_id"], aprobado=aprobado, revisor=revisor,
                           huella_revisada=solicitud["pendiente"]["huella_propuesta"][:12],
                           codigo_confirmacion=solicitud["codigo_confirmacion"], origen=origen)


def demostracion(directorio: Path, interactivo: bool = False) -> dict:
    copia = directorio / "registro_prompts.json"
    shutil.copy(RUTA_REGISTRO, copia)
    registro = RegistroDePrompts(copia)
    gestor = GestorSupervision(registro, ruta_solicitudes=directorio / "solicitudes.json")
    activa_inicial = registro.activa()["huella"]
    resultados: dict = {"activa_inicial": activa_inicial}

    print("== Caso 1: aprobación")
    s1 = gestor.iniciar(NOMBRE_PROMPT_RAG, plantillas_propuesta_academica(), "demo-bloque32", NOTA_PROPUESTA_ACADEMICA)
    estado = gestor.grafo.get_state(gestor.config(s1["thread_id"]))
    print(f"  thread_id={s1['thread_id']}  next={estado.next}  (interrumpido)")
    print(f"  Propuesta v{s1['pendiente']['version_propuesta']} huella={s1['pendiente']['huella_propuesta'][:12]} "
          f"estado en registro={registro.por_huella(s1['pendiente']['huella_propuesta'])['estado']}; "
          f"activa sigue siendo {registro.activa()['huella']}")
    print("  Diff pendiente de revisión:\n" + "".join("    " + l for l in s1["pendiente"]["diff"].splitlines(True)))
    resultados["interrumpido"] = estado.next == ("solicitar_supervision",)
    resultados["activa_antes_de_aprobar"] = registro.activa()["huella"]

    print("  Un agente intenta Command(resume=True):")
    gestor.grafo.invoke(Command(resume=True), gestor.config(s1["thread_id"]))
    estado = gestor.grafo.get_state(gestor.config(s1["thread_id"]))
    print(f"    → no aprueba; sigue pendiente ({estado.next}); motivo: {estado.values['ultimo_error']}")
    resultados["agente_no_aprueba"] = registro.activa()["huella"] == activa_inicial

    if interactivo:
        print(f"  Código de confirmación (mostrar solo a quien revisa): {s1['codigo_confirmacion']}")
        texto = input("  Escribe exactamente 'aprobar' o 'rechazar' (otra cosa = sin decisión): ").strip()
        if texto not in ("aprobar", "rechazar"):
            print(f"  {texto!r} no es una decisión: la propuesta queda pendiente y NO se activa.")
            resultados["caso1"] = "sin_decision"
        else:
            revisor = input("  Nombre de quien revisa (no se autentica): ").strip() or "sin-nombre"
            codigo = input("  Código de confirmación: ").strip()
            try:
                r = _decidir(gestor, {**s1, "codigo_confirmacion": codigo}, texto == "aprobar", "humano_cli", revisor)
                resultados["caso1"] = r["resultado"]
            except DecisionInvalidaError as error:
                print(f"  Decisión inválida: {error}. No se activa.")
                resultados["caso1"] = "decision_invalida"
    else:
        print("  Decisión SIMULADA de la demostración: aprobar")
        resultados["caso1"] = _decidir(gestor, s1, True)["resultado"]
    print(f"  Resultado: {resultados['caso1']}; activa ahora: v{registro.activa()['version']} ({registro.activa()['huella']})")
    resultados["activa_tras_caso1"] = registro.activa()["huella"]

    print("\n== Caso 2: rechazo (otra propuesta, otro thread_id)")
    activa_antes = registro.activa()["huella"]
    s2 = gestor.iniciar(NOMBRE_PROMPT_RAG, _propuesta_rechazo(), "demo-bloque32",
                        "PROPUESTA ACADÉMICA para demostrar el rechazo: debilita la regla 3.")
    print(f"  thread_id={s2['thread_id']} (distinto: {s2['thread_id'] != s1['thread_id']}); interrumpido; "
          f"propuesta {s2['pendiente']['huella_propuesta'][:12]}")
    try:
        gestor.resolver(s2["thread_id"], aprobado="no", revisor="x", huella_revisada=s2["pendiente"]["huella_propuesta"],
                        codigo_confirmacion=s2["codigo_confirmacion"], origen="simulada_demo")
    except DecisionInvalidaError as error:
        print(f"  aprobado='no' se rechaza como valor inválido: {error}")
    print("  Decisión SIMULADA de la demostración: rechazar")
    r2 = _decidir(gestor, s2, False)
    resultados["caso2"] = r2["resultado"]
    resultados["activa_sin_cambio_tras_rechazo"] = registro.activa()["huella"] == activa_antes
    print(f"  Resultado: {r2['resultado']}; activa sin cambio: {resultados['activa_sin_cambio_tras_rechazo']}")
    try:
        _decidir(gestor, s2, True)
    except Exception as error:  # noqa: BLE001 - se muestra el bloqueo esperado
        print(f"  Reintentar sobre el hilo resuelto: bloqueado ({type(error).__name__})")

    print("\n== Caso 3: reinicio con InMemorySaver (no durable)")
    s3 = gestor.iniciar(NOMBRE_PROMPT_RAG, {**_propuesta_rechazo(), "human": _propuesta_rechazo()["human"] + " "},
                        "demo-bloque32", "PROPUESTA ACADÉMICA para demostrar la pérdida del estado.")
    reiniciado = GestorSupervision(RegistroDePrompts(copia), ruta_solicitudes=directorio / "solicitudes.json")
    huerfanas = reiniciado.huerfanas()
    estado_propuesta = reiniciado.registro.por_huella(s3["pendiente"]["huella_propuesta"])["estado"]
    print(f"  Tras 'reiniciar' (nuevo InMemorySaver): solicitudes huérfanas={huerfanas}; "
          f"la propuesta sigue en '{estado_propuesta}' y no se activó.")
    resultados["huerfana_detectada"] = s3["thread_id"] in huerfanas and estado_propuesta == "propuesta"
    return resultados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interactivo", action="store_true")
    args = parser.parse_args(argv)
    huella_original = _sha(RUTA_REGISTRO)
    with tempfile.TemporaryDirectory(prefix="supervision_demo_") as directorio:
        resultados = demostracion(Path(directorio), args.interactivo)
    sin_cambios = _sha(RUTA_REGISTRO) == huella_original
    print(f"\nRegistro versionado sin cambios: {sin_cambios}")
    comprobaciones = [resultados["interrumpido"], resultados["agente_no_aprueba"],
                      resultados["activa_antes_de_aprobar"] == resultados["activa_inicial"],
                      resultados["caso2"].startswith("rechazada"), resultados["activa_sin_cambio_tras_rechazo"],
                      resultados["huerfana_detectada"], sin_cambios]
    if not args.interactivo:
        comprobaciones.append(resultados["caso1"] == "activada"
                              and resultados["activa_tras_caso1"] != resultados["activa_inicial"])
    return 0 if all(comprobaciones) else 1


if __name__ == "__main__":
    sys.exit(main())
