"""Rúbrica del Gate 2: promedio ponderado + criterios no compensables (AUTOEVALUACIÓN).

    promedio = sum(puntajes[d] * PESOS_GATE2[d] for d in PESOS_GATE2)

- Puntajes 0–100 por dimensión, con evidencia, en `data/gate2/autoevaluacion.json`. Son una
  AUTOEVALUACIÓN; la evaluación oficial del curso no existe en el repositorio (queda en null).
- Los 4 criterios no compensables se verifican ejecutando sus pruebas reales de `tests/test_gate2.py`.
  Si alguno falla o no se pudo verificar, el Gate no queda listo aunque el promedio sea >= 80.
- Estados posibles: LISTO_PARA_REVISION, PENDIENTE, NO_VERIFICADO. Nunca GATE_APROBADO_OFICIALMENTE.

Uso: python -m src.rubrica_gate2            (ejecuta las 4 pruebas no compensables con pytest)
     python -m src.rubrica_gate2 --sin-pruebas   (los no compensables quedan NO_VERIFICADO)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from src.rag.configuracion import RAIZ_REPO

PESOS_GATE2 = {
    "pipeline_funcional": 0.25,
    "recuperacion_citacion": 0.15,
    "costo_latencia": 0.10,
    "personalizacion": 0.15,
    "observabilidad": 0.15,
    "seguridad_gobernanza": 0.20,
}
UMBRAL_APROBACION = 80
NO_COMPENSABLES = {
    "pipeline_punta_a_punta": "test_pipeline_sin_excepciones",
    "respuestas_con_fuentes_validas": "test_respuesta_cita_fuente",
    "logs_sin_contenido_crudo": "test_logs_sin_contenido_crudo",
    "supervision_humana_pausa_y_reanuda": "test_supervision_pausa_y_reanuda",
}
ESTADOS = ("LISTO_PARA_REVISION", "PENDIENTE", "NO_VERIFICADO")
RUTA_AUTOEVALUACION = RAIZ_REPO / "data" / "gate2" / "autoevaluacion.json"
ARCHIVO_PRUEBAS = "tests/test_gate2.py"


def validar_puntaje(valor, dimension: str) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= 100:
        raise ValueError(f"{dimension}: el puntaje debe ser un entero 0–100 o null; se recibió {valor!r}.")
    return valor


def promedio_ponderado(puntajes: dict[str, int | None]) -> float | None:
    """None si falta alguna dimensión: un promedio parcial no se presenta como total."""
    if set(puntajes) != set(PESOS_GATE2):
        raise ValueError(f"Dimensiones esperadas: {sorted(PESOS_GATE2)}.")
    valores = {d: validar_puntaje(v, d) for d, v in puntajes.items()}
    if any(v is None for v in valores.values()):
        return None
    return round(sum(valores[d] * PESOS_GATE2[d] for d in PESOS_GATE2), 2)


def evaluar(puntajes: dict[str, int | None], no_compensables: dict[str, bool | None]) -> dict:
    """`no_compensables`: True (verificado y cumple), False (falla) o None (no verificado)."""
    if set(no_compensables) != set(NO_COMPENSABLES):
        raise ValueError(f"No compensables esperados: {sorted(NO_COMPENSABLES)}.")
    for nombre, valor in no_compensables.items():
        if valor is not None and not isinstance(valor, bool):
            raise ValueError(f"{nombre}: debe ser True, False o None.")
    promedio = promedio_ponderado(puntajes)
    fallidos = [n for n, v in no_compensables.items() if v is False]
    sin_verificar = [n for n, v in no_compensables.items() if v is None]
    pendientes = [d for d, v in puntajes.items() if v is None]
    if sin_verificar:
        estado, motivo = "NO_VERIFICADO", f"No compensables sin verificar: {sin_verificar}"
    elif fallidos:
        estado, motivo = "PENDIENTE", f"No compensables incumplidos: {fallidos}"
    elif promedio is None:
        estado, motivo = "PENDIENTE", f"Dimensiones sin puntaje: {pendientes}"
    elif promedio < UMBRAL_APROBACION:
        estado, motivo = "PENDIENTE", f"Promedio {promedio} < {UMBRAL_APROBACION}"
    else:
        estado, motivo = "LISTO_PARA_REVISION", (f"Promedio {promedio} >= {UMBRAL_APROBACION} y los 4 no compensables "
                                                  "verificados. Es una autoevaluación: la aprobación depende del curso.")
    return {"estado": estado, "motivo": motivo, "promedio": promedio, "umbral": UMBRAL_APROBACION,
            "no_compensables": dict(no_compensables), "dimensiones_pendientes": pendientes,
            "tipo": "autoevaluacion", "evaluacion_oficial": None}


def cargar_autoevaluacion(ruta: Path = RUTA_AUTOEVALUACION) -> dict:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if datos.get("tipo") != "autoevaluacion" or datos.get("evaluacion_oficial") is not None:
        raise ValueError("El archivo debe declarar tipo 'autoevaluacion' y evaluacion_oficial null.")
    for dimension in PESOS_GATE2:
        entrada = datos["dimensiones"].get(dimension)
        if not entrada or not entrada.get("evidencia"):
            raise ValueError(f"{dimension}: falta la evidencia.")
        validar_puntaje(entrada.get("puntaje"), dimension)
    return datos


def verificar_no_compensables(raiz: Path = RAIZ_REPO) -> dict[str, bool | None]:
    """Ejecuta cada prueba no compensable con pytest (offline). None si pytest no pudo ejecutarse."""
    resultados: dict[str, bool | None] = {}
    for nombre, prueba in NO_COMPENSABLES.items():
        try:
            proceso = subprocess.run([sys.executable, "-m", "pytest", "-q", f"{ARCHIVO_PRUEBAS}::{prueba}"],
                                     cwd=raiz, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            resultados[nombre] = None
            continue
        resultados[nombre] = True if proceso.returncode == 0 else (False if proceso.returncode == 1 else None)
    return resultados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-pruebas", action="store_true")
    args = parser.parse_args(argv)
    datos = cargar_autoevaluacion()
    puntajes = {d: datos["dimensiones"][d]["puntaje"] for d in PESOS_GATE2}
    no_compensables = ({n: None for n in NO_COMPENSABLES} if args.sin_pruebas else verificar_no_compensables())
    informe = evaluar(puntajes, no_compensables)
    print("AUTOEVALUACIÓN del Gate 2 (no es la evaluación oficial del curso)\n")
    for d, peso in PESOS_GATE2.items():
        print(f"  {d:<24} peso {peso:.2f}  puntaje {puntajes[d]}")
    print(f"\n  Promedio ponderado: {informe['promedio']} (umbral {UMBRAL_APROBACION})")
    for nombre, valor in informe["no_compensables"].items():
        print(f"  [{ {True: 'CUMPLE', False: 'FALLA', None: 'NO VERIFICADO'}[valor] }] {nombre}")
    print(f"\nEstado: {informe['estado']} — {informe['motivo']}")
    return 0 if informe["estado"] == "LISTO_PARA_REVISION" else 1


if __name__ == "__main__":
    sys.exit(main())
