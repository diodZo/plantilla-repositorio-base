"""Selecciona hasta 5 F1 bajos + 5 altos para revisión MANUAL.
Ejecutar: python -m src.preparar_revision_bloque17 --entrada docs/resultados_metricas.json
No evalúa automáticamente factualidad ni genera respuestas con Gemini.
"""
import argparse
import json
from pathlib import Path


def seleccionar_muestra(resultados: list[dict], por_extremo: int = 5) -> list[dict]:
    """Ordena por F1; devuelve casos únicos de ambos extremos."""
    for i, caso in enumerate(resultados):
        if not all(k in caso for k in ("consulta", "respuesta", "referencia", "f1")):
            raise ValueError(f"Caso {i} sin consulta, respuesta, referencia o f1")
        if not isinstance(caso["f1"], (float, int)):
            raise ValueError(f"Caso {i} tiene f1 no numérico")
    indices = sorted(range(len(resultados)), key=lambda i: resultados[i]["f1"])
    elegidos = indices[:por_extremo] + indices[-por_extremo:]
    unicos = list(dict.fromkeys(elegidos))
    return [resultados[i] for i in unicos]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", default="docs/resultados_metricas.json")
    parser.add_argument("--salida", default="docs/revision_manual_bloque17.json")
    args = parser.parse_args()
    ruta = Path(args.entrada)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Primero genera resultados del Bloque 16.")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if isinstance(datos, dict) and isinstance(datos.get("resultados"), list):
        datos = datos["resultados"]
    if not isinstance(datos, list):
        raise SystemExit("El JSON debe ser una lista o un objeto con clave 'resultados'.")
    if len(datos) < 20:
        print(f"Aviso: hay {len(datos)} resultados; la actividad exige al menos 20.")
    muestra = seleccionar_muestra(datos)
    revision = [
        {
            "consulta": caso["consulta"],
            "referencia": caso["referencia"],
            "respuesta": caso["respuesta"],
            "f1": caso["f1"],
            "correccion_factual": "pendiente",
            "completitud": "pendiente",
            "contradiccion": "pendiente",
            "nota": "",
        }
        for caso in muestra
    ]
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(revision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seleccionados {len(revision)} casos para revisión manual: {salida}")
    print("Importante: completar rúbrica y notas leyendo cada respuesta y su referencia.")


if __name__ == "__main__":
    main()
