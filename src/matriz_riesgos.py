"""CLI 3 del Bloque 32: matriz de riesgos con puntajes, categorías oficiales y sensibilidad.

Uso (desde la raíz):
    python -m src.matriz_riesgos
    python -m src.matriz_riesgos --json     # salida JSON con los valores calculados

Solo lectura de data/gobernanza/matriz_riesgos.json.
"""
from __future__ import annotations

import argparse
import json
import sys

from src.gobernanza.matriz_riesgos import (
    CATEGORIAS_CON_SUPERVISION, RUTA_MATRIZ, cargar_matriz, ordenar, sin_supervision_requerida, tabla_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    riesgos = ordenar(cargar_matriz(RUTA_MATRIZ))
    if args.json:
        print(json.dumps([r.como_dict() for r in riesgos], ensure_ascii=False, indent=2))
        return 0
    print(f"Matriz de riesgos ({len(riesgos)} riesgos, orden descendente por puntaje)\n")
    print(tabla_markdown(riesgos))
    altos = [r for r in riesgos if r.categoria in CATEGORIAS_CON_SUPERVISION]
    print(f"\nALTO/CRITICO: {len(altos)}; sin control humano identificado: {sin_supervision_requerida(riesgos) or 'ninguno'}")
    for r in altos:
        print(f"  {r.id} → {r.supervision['control']} [{r.supervision['estado']}]")
    print(f"Al límite: {[r.id for r in riesgos if r.al_limite]}")
    return 1 if sin_supervision_requerida(riesgos) else 0


if __name__ == "__main__":
    sys.exit(main())
