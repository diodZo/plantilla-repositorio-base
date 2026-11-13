"""Bloque 26: compara recuperación vectorial, léxica (BM25) e híbrida (RRF) con Hit@3 y Hit@5.

Desde la raíz (requiere el índice del Bloque 24; una llamada a embed_query por consulta, sin generación):
  python -m src.evaluar_recuperacion
  python -m src.evaluar_recuperacion --salida docs/evaluacion_recuperacion.json
  python -m src.evaluar_recuperacion --coleccion OTRA --chunk-size 500 --chunk-overlap 75 --estrategia recursivo
  python -m src.evaluar_recuperacion --indice markdown --expandir --conjunto validacion

Por defecto evalúa el índice base, sin expansión, con el conjunto de desarrollo, para que las
cifras documentadas sean reproducibles. La CLI de consultas usa otros valores por defecto.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE26_MD, ESTRATEGIAS
from src.rag.embeddings import EmbeddingsConReintentos, crear_embeddings_gemini
from src.rag.errores import ErrorRAG
from src.rag.evaluacion import CONJUNTOS, METODOS, cargar_consultas, evaluar_consulta, primer_acierto, resumir
from src.rag.indexador import cargar_indice
from src.rag.lexico import IndiceBM25


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indice", choices=("base", "markdown"), default="base")
    parser.add_argument("--conjunto", choices=tuple(CONJUNTOS), default="desarrollo")
    parser.add_argument("--coleccion")
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--chunk-overlap", type=int)
    parser.add_argument("--estrategia", choices=ESTRATEGIAS)
    parser.add_argument("--candidatos", type=int, default=20, help="Candidatos por método antes de fusionar")
    parser.add_argument("--k-rrf", type=int, default=60)
    parser.add_argument("--expandir", action="store_true", help="Expande cada resultado a su sección (small-to-big)")
    parser.add_argument("--salida", type=Path, help="Archivo JSON donde guardar los resultados")
    opciones = parser.parse_args(argv)
    cambios = {k: v for k, v in {"nombre_coleccion": opciones.coleccion, "chunk_size": opciones.chunk_size,
                                 "chunk_overlap": opciones.chunk_overlap,
                                 "estrategia": opciones.estrategia}.items() if v is not None}
    try:
        base = CONFIG_BLOQUE26_MD if opciones.indice == "markdown" else CONFIG_BLOQUE24
        config = base.con(**cambios) if cambios else base
        embeddings = EmbeddingsConReintentos(crear_embeddings_gemini(config.modelo_embeddings))
        almacen = cargar_indice(config, embeddings)
        indice = IndiceBM25.desde_almacen(almacen)
        print(f"Colección {config.nombre_coleccion}: {len(indice.documentos)} chunks "
              f"({config.estrategia} {config.chunk_size}/{config.chunk_overlap}); "
              f"candidatos={opciones.candidatos}, k_rrf={opciones.k_rrf}, expandir={opciones.expandir}\n")
        resultados = [evaluar_consulta(almacen, indice, c, candidatos=opciones.candidatos, k_rrf=opciones.k_rrf,
                                       expandir=opciones.expandir)
                      for c in cargar_consultas(CONJUNTOS[opciones.conjunto])]
        print(f"{'consulta':<15}" + "".join(f"{m:>22}" for m in METODOS))
        print(f"{'':<15}" + "".join(f"{'pos.evid / pos.fuente':>22}" for _ in METODOS))
        for r in resultados:
            celdas = []
            for metodo in METODOS:
                if not r.consulta.fuentes:
                    celdas.append(f"top: {(r.detalle[metodo] or [{'fuente': '—'}])[0]['fuente']}"[:21])
                    continue
                estricta = primer_acierto(r.rankings[metodo], r.consulta, True)
                fuente = primer_acierto(r.rankings[metodo], r.consulta, False)
                celdas.append(f"{estricta or '>20'} / {fuente or '>20'}")
            print(f"{r.consulta.id:<15}" + "".join(f"{c:>22}" for c in celdas))
        resumen = resumir(resultados)
        print("\nHit@k (consultas con fuente esperada):")
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        print(f"\nembed_documents={embeddings.llamadas_documentos} (no reindexa), embed_query={embeddings.llamadas_consulta}")
        if opciones.salida:
            salida = {
                "coleccion": config.nombre_coleccion, "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap, "estrategia": config.estrategia,
                "conjunto": opciones.conjunto,
                "candidatos": opciones.candidatos, "k_rrf": opciones.k_rrf, "expandir": opciones.expandir,
                "resumen": resumen,
                "consultas": [{
                    "id": r.consulta.id, "pregunta": r.consulta.pregunta,
                    "primer_acierto_evidencia": {m: primer_acierto(r.rankings[m], r.consulta, True) for m in METODOS},
                    "primer_acierto_fuente": {m: primer_acierto(r.rankings[m], r.consulta, False) for m in METODOS},
                    "top5": r.detalle,
                } for r in resultados],
            }
            opciones.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Resultados guardados en {opciones.salida}")
        return 0
    except ErrorRAG as error:
        print(f"Error ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
