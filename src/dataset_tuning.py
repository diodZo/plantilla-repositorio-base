"""CLI del Bloque 29: valida el dataset de personalización y prepara el tuning SIN llamar a la API.

Uso (desde la raíz):
    python -m src.dataset_tuning
    python -m src.dataset_tuning --respuestas ruta/respuestas.json --origen gemini_base

Código de salida: 0 si no hay errores (puede haber advertencias); 1 si hay errores.
No crea clientes de Gemini ni trabajos de tuning.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.personalizacion.balance import chequear_balance, formatear_balance
from src.personalizacion.configuracion_tuning import (
    construir_config_peft, dataset_gcs_pendiente, info_sdk, verificar_compatibilidad,
)
from src.personalizacion.dataset import (
    MINIMO_EJEMPLOS_ENTRENAMIENTO, RUTA_ENTRENAMIENTO, RUTA_VALIDACION, cargar_ejemplos, construir_tuning_dataset,
)
from src.personalizacion.evaluacion import cargar_respuestas, evaluar_respuestas, respuestas_de_referencia
from src.personalizacion.validacion import advertencias, errores, solapamiento, validar_dataset


def _imprimir_problemas(titulo: str, problemas) -> None:
    print(f"\n== {titulo}: {len(errores(problemas))} errores, {len(advertencias(problemas))} advertencias")
    for problema in problemas:
        print(f"  - {problema}")


def _imprimir_evaluacion(resultado: dict) -> None:
    print(f"\n== Evaluación offline ({resultado['tipo']}, origen={resultado['origen']}, n={resultado['n']})")
    for check, tasa in resultado["tasas"].items():
        print(f"  {check:<20} {tasa:.0%}")
    print(f"  incumplimiento de formato: {resultado['incumplimiento_formato']:.0%}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entrenamiento", type=Path, default=RUTA_ENTRENAMIENTO)
    parser.add_argument("--validacion", type=Path, default=RUTA_VALIDACION)
    parser.add_argument("--respuestas", type=Path, help="JSON con respuestas reales a evaluar (mismo orden que validación)")
    parser.add_argument("--origen", default="respuestas_externas", help="Etiqueta del origen de --respuestas")
    args = parser.parse_args(argv)

    entrenamiento = cargar_ejemplos(args.entrenamiento)
    validacion = cargar_ejemplos(args.validacion)

    p_ent = validar_dataset(entrenamiento)
    p_val = validar_dataset(validacion)
    p_fuga = solapamiento(entrenamiento, validacion)
    _imprimir_problemas(f"Entrenamiento ({len(entrenamiento)} ejemplos)", p_ent)
    _imprimir_problemas(f"Validación ({len(validacion)} ejemplos)", p_val)
    _imprimir_problemas("Solapamiento entrenamiento/validación", p_fuga)

    total_errores = len(errores(p_ent + p_val + p_fuga))
    if len(entrenamiento) < MINIMO_EJEMPLOS_ENTRENAMIENTO:
        print(f"\nERROR: {len(entrenamiento)} ejemplos de entrenamiento; la actividad exige al menos "
              f"{MINIMO_EJEMPLOS_ENTRENAMIENTO} (mínimo del curso, no de la API).")
        total_errores += 1

    print("\n== Balance (entrenamiento)")
    print(formatear_balance(chequear_balance(entrenamiento)))
    print("\n== Balance (validación)")
    print(formatear_balance(chequear_balance(validacion)))

    if args.respuestas:
        _imprimir_evaluacion(evaluar_respuestas(validacion, cargar_respuestas(args.respuestas), args.origen))
    else:
        resultado = evaluar_respuestas(validacion, respuestas_de_referencia(validacion), "control_referencia")
        _imprimir_evaluacion(resultado)
        print("  (Control del evaluador con las salidas esperadas: NO mide ningún modelo.)")

    sdk = info_sdk()
    print("\n== SDK google-genai (introspección local)")
    if not sdk["instalado"]:
        print(f"  No instalado: {sdk['error']}")
        return 1 if total_errores else 0
    print(f"  versión {sdk['version']}; tipos: " + ", ".join(f"{n}={'sí' if ok else 'no'}" for n, ok in sdk["tipos"].items()))

    if total_errores:
        print("\nHay errores: no se construyen objetos de tuning.")
        return 1

    dataset = construir_tuning_dataset(entrenamiento)
    config = construir_config_peft()
    print(f"  TuningDataset local con {len(dataset.examples)} TuningExample.")
    print(f"  CreateTuningJobConfig local: tuning_mode={config.tuning_mode.name}, adapter_size={config.adapter_size.name}")
    for etiqueta, ds in (("ejemplos inline", dataset), ("gcs_uri de marcador", dataset_gcs_pendiente())):
        compat = verificar_compatibilidad(ds, config)
        if not compat["verificable"]:
            print(f"  [{etiqueta}] compatibilidad no verificable: {compat['motivo']}")
            continue
        for modo in ("gemini_developer_api", "vertex"):
            motivo = compat[modo]
            print(f"  [{etiqueta} + PEFT] {modo}: {'el SDK la aceptaría' if motivo is None else 'RECHAZADA - ' + motivo}")
    print("\nNo se creó ningún trabajo de tuning ni se llamó a la API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
