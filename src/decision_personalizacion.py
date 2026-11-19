"""CLI del Bloque 30: aplica el método de decisión y genera `docs/decision_personalizacion.md`.

Uso (desde la raíz):
    python -m src.decision_personalizacion             # imprime puntuaciones y escribe el documento
    python -m src.decision_personalizacion --no-escribir
    python -m src.decision_personalizacion --respuestas-base data/personalizacion/respuestas_modelo_base.json

Sin llamadas a la API: la evidencia sale del dataset, del historial de git y de archivos del repositorio.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.personalizacion.balance import chequear_balance
from src.personalizacion.configuracion_tuning import (
    construir_config_peft, dataset_gcs_pendiente, info_sdk, verificar_compatibilidad,
)
from src.personalizacion.dataset import RAIZ_REPO, RUTA_ENTRENAMIENTO, RUTA_VALIDACION, cargar_ejemplos, construir_tuning_dataset
from src.personalizacion.decision import (
    EJEMPLO_OFICIAL_CURSO, HIPOTESIS_INICIAL, RUTA_RESPUESTAS_BASE, escenarios_no_verificados, fechas_git, puntuar,
    recomendar, recopilar_evidencia, valores_de,
)
from src.personalizacion.documento_decision import generar_documento
from src.personalizacion.validacion import errores, validar_dataset

RUTA_DOCUMENTO = RAIZ_REPO / "docs" / "decision_personalizacion.md"


def construir(ruta_respuestas: Path = RUTA_RESPUESTAS_BASE) -> tuple[str, dict]:
    entrenamiento = cargar_ejemplos(RUTA_ENTRENAMIENTO)
    validacion = cargar_ejemplos(RUTA_VALIDACION)
    if errores(validar_dataset(entrenamiento)) or errores(validar_dataset(validacion)):
        raise SystemExit("El dataset tiene errores: ejecuta primero python -m src.dataset_tuning")

    fechas = fechas_git(RAIZ_REPO)
    evidencias = recopilar_evidencia(len(entrenamiento) + len(validacion), RAIZ_REPO, ruta_respuestas, fechas)
    resultado = puntuar(valores_de(evidencias))
    resultado_hipotesis = puntuar(HIPOTESIS_INICIAL)

    sdk = info_sdk()
    compatibilidad = {}
    if sdk.get("instalado"):
        config = construir_config_peft()
        compatibilidad = {
            "ejemplos inline": verificar_compatibilidad(construir_tuning_dataset(entrenamiento), config),
            "dataset en Cloud Storage": verificar_compatibilidad(dataset_gcs_pendiente(), config),
        }
    referencia = f"HEAD del {fechas[2].isoformat()}" if fechas else "historial de git no disponible"
    documento = generar_documento(
        conteos_entrenamiento=chequear_balance(entrenamiento).conteos,
        conteos_validacion=chequear_balance(validacion).conteos,
        evidencias=evidencias,
        resultado=resultado,
        resultado_hipotesis=resultado_hipotesis,
        sdk=sdk,
        compatibilidad=compatibilidad,
        referencia_git=referencia,
    )
    return documento, {"evidencias": evidencias, "resultado": resultado, "hipotesis": resultado_hipotesis}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=RUTA_DOCUMENTO)
    parser.add_argument("--no-escribir", action="store_true", help="Solo imprime; no escribe el documento")
    parser.add_argument("--respuestas-base", type=Path, default=RUTA_RESPUESTAS_BASE,
                        help="Muestra de respuestas reales del modelo base (si existe)")
    args = parser.parse_args(argv)

    documento, datos = construir(args.respuestas_base)
    print("== Criterios (evidencia del repositorio)")
    for e in datos["evidencias"]:
        print(f"  {e.criterio:<38} {str(e.valor):<6} [{e.estado}] {e.detalle}")
    for titulo, resultado in (("comprobados", datos["resultado"]), ("de la hipótesis inicial", datos["hipotesis"]),
                              ("del ejemplo oficial del curso", puntuar(EJEMPLO_OFICIAL_CURSO))):
        etiqueta = " [PROVISIONAL: hay criterios sin verificar]" if resultado.provisional else ""
        print(f"\n== Puntuación con valores {titulo}{etiqueta}: {resultado.puntos}")
        print(f"   Empatadas en primer lugar: {resultado.empatadas}" if resultado.hay_empate
              else f"   Primer lugar: {resultado.ganadora}")
        if resultado.no_verificados:
            print(f"   No verificados: {resultado.no_verificados}; máximo posible: {resultado.maximo_posible}")
            for asignacion, r in escenarios_no_verificados(valores_de(datos["evidencias"])):
                print(f"   Si {asignacion}: {r.puntos} -> primer lugar {r.empatadas}")
    rec = recomendar(datos["resultado"])
    print(f"\n== Recomendación\n   Inmediata: {rec['inmediata']}\n   Futura: {rec['futura']}\n   Motivo: {rec['motivo']}")

    if not args.no_escribir:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(documento, encoding="utf-8", newline="\n")
        print(f"\nDocumento escrito en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
