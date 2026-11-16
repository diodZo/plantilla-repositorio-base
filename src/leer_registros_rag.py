"""Bloque 28: lee registros_latencia_costo.jsonl y resume latencia, tokens y costos.

  python -m src.leer_registros_rag                    # estadísticas en consola
  python -m src.leer_registros_rag --informe          # además regenera docs/resultados_bloque28.md
  python -m src.leer_registros_rag --registro otra_ruta.jsonl

Solo usa los registros: no llama a ninguna API. Las líneas corruptas se informan, no se ignoran.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.rag.configuracion import RAIZ_REPO
from src.rag.observabilidad import ARCHIVO_REGISTROS, ETAPAS, estadisticas, leer_registros

ARCHIVO_INFORME = RAIZ_REPO / "docs" / "resultados_bloque28.md"


def _n(valor, decimales: int = 1) -> str:
    if valor is None:
        return "—"
    return f"{valor:.{decimales}f}" if isinstance(valor, float) else str(valor)


def _usd(valor) -> str:
    return "—" if valor is None else f"{valor:.8f}"


def tabla_consultas(registros: list[dict]) -> list[str]:
    lineas = ["| Ejecución | Caso | k | Estado | Total ms | Embed ms | Búsqueda ms | Expansión ms | Prompt ms | Generación ms | "
              "Sobrecarga ms | Tokens entrada | Tokens salida (razonamiento) | Total tokens | Secciones | Car. contexto | Costo gen. USD | Fuentes |",
              "|" + "---|" * 18]
    for r in registros:
        t = r.get("tiempos_ms", {})
        g = (r.get("tokens") or {}).get("generacion") or {}
        costo = (r.get("costo_usd") or {}).get("total_conocido_usd")
        salida = _n(g.get("salida")) + (f" ({g['razonamiento']})" if g.get("razonamiento") is not None else "")
        lineas.append(
            f"| {r.get('id_ejecucion', '')[:22]} | {r.get('caso', '—')} | {r.get('k')} | {r.get('estado')} | "
            f"{_n(r.get('tiempo_total_ms'))} | {_n(t.get('embed_query'))} | {_n(t.get('busqueda_vectorial'))} | "
            f"{_n(t.get('expansion_contexto'))} | {_n(t.get('construccion_prompt'))} | {_n(t.get('generacion'))} | "
            f"{_n(r.get('sobrecarga_ms'))} | {_n(g.get('entrada'))} | {salida} | {_n(g.get('total'))} | "
            f"{(r.get('recuperacion') or {}).get('secciones_unicas', '—')} | {_n(r.get('caracteres_contexto'))} | "
            f"{_usd(costo)} | {', '.join(r.get('fuentes', []))} |")
    return lineas


def escribir_informe(registros: list[dict], errores_lectura: list[dict], ruta: Path = ARCHIVO_INFORME) -> None:
    est = estadisticas(registros)
    lineas = [
        "# Resultados del Bloque 28 — latencia, tokens y costo",
        "",
        "> Generado por `python -m src.leer_registros_rag --informe` a partir de `registros_latencia_costo.jsonl`. "
        "Solo contiene datos **reales** registrados; no hay cifras ilustrativas. El análisis está en `docs/ensayo-bloque28.md`.",
        "",
        f"Registros leídos: {len(registros)} · consultas completas reales: {est['consultas']} · "
        f"consultas con error: {est['errores']} · líneas ilegibles: {len(errores_lectura)}.",
        "",
        "## Consultas registradas",
        "",
        *tabla_consultas(registros),
        "",
        "## Estadísticas (consultas reales completas)",
        "",
        f"Con n = {est['consultas']}, estas cifras describen solo estas ejecuciones; **no** representan el rendimiento habitual.",
        "",
        "| Medida | n | Media | Mediana | Mínimo | Máximo |",
        "|---|---|---|---|---|---|",
    ]
    filas = [("Total (ms)", est["total_ms"]), ("Sobrecarga fuera de etapas (ms)", est["sobrecarga_ms"])]
    filas += [(f"Etapa {e} (ms)", est["etapas_ms"][e]) for e in ETAPAS if e in est["etapas_ms"]]
    filas += [("Tokens de entrada", est["tokens_entrada"]), ("Tokens de salida", est["tokens_salida"]),
              ("Tokens de razonamiento (incluidos en salida)", est["tokens_razonamiento"]),
              ("Caracteres de prompt por token de entrada", est["caracteres_prompt_por_token_entrada"])]
    for nombre, r in filas:
        lineas.append(f"| {nombre} | {r['n']} | {_n(r['media'], 2)} | {_n(r['mediana'], 2)} | {_n(r['minimo'], 2)} | {_n(r['maximo'], 2)} |")
    c = est["costo_generacion_usd"]
    lineas.append(f"| Costo de generación (USD, estimado a tarifa de pago) | {c['n']} | {_usd(c['media'])} | "
                  f"{_usd(c['mediana'])} | {_usd(c['minimo'])} | {_usd(c['maximo'])} |")
    tarifas = next((r["tarifas"] for r in registros if r.get("tarifas")), None)
    if tarifas:
        lineas += ["", f"Tarifas aplicadas ({tarifas['tipo']}, consultadas {tarifas['fecha_consulta']}): "
                   f"generación {tarifas.get('generacion')}, embedding {tarifas.get('embedding')} USD por millón de tokens. "
                   f"Fuente: {tarifas['fuente']}. Son costos estimados a partir de tokens; no son importes facturados."]
    errores = [r for r in registros if r.get("estado") == "error"]
    if errores:
        lineas += ["", "## Consultas con error (no se excluyen del registro)", ""]
        lineas += [f"- {r.get('timestamp')} {r.get('caso')}: {r['error']['tipo']} — {r['error']['mensaje']} "
                   f"(etapas fallidas: {r['error']['etapas_fallidas']})" for r in errores]
    if errores_lectura:
        lineas += ["", "## Líneas ilegibles", ""] + [f"- línea {e['linea']}: {e['error']}" for e in errores_lectura]
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registro", type=Path, default=ARCHIVO_REGISTROS)
    parser.add_argument("--informe", action="store_true")
    parser.add_argument("--salida-informe", type=Path, default=ARCHIVO_INFORME)
    opciones = parser.parse_args(argv)
    registros, errores = leer_registros(opciones.registro)
    if not registros:
        print(f"No hay registros en {opciones.registro}.", file=sys.stderr)
        return 1
    print(json.dumps(estadisticas(registros), ensure_ascii=False, indent=2))
    for e in errores:
        print(f"Línea ilegible {e['linea']}: {e['error']}", file=sys.stderr)
    if opciones.informe:
        escribir_informe(registros, errores, opciones.salida_informe)
        print(f"Informe: {opciones.salida_informe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
