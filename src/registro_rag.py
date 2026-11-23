"""Bloque 28: consultas RAG instrumentadas (latencia, tokens y costo) con registro JSONL.

RUTA HEREDADA (no recomendada desde el Gate 2): mide latencia y costo, pero no aplica el filtro de
inyección y su registro guarda la pregunta completa. Para generar respuestas usa `python -m src.servicio_rag`.

Configuración: índice markdown + vectorial + expansión, k=3 (predeterminada de la CLI del Bloque 26).

Desde la raíz del repositorio:
  python -m src.rag.preflight                                   # diagnóstico local, sin Gemini
  python -m src.registro_rag --comparar-ruta                     # ruta anterior vs instrumentada (solo embed_query)
  python -m src.registro_rag                                     # 3 casos del Bloque 27, k=3 (3 embed_query + 3 generaciones)
  python -m src.registro_rag --casos c01-backoff --k 6           # misma pregunta con k=6
  python -m src.registro_rag --pregunta "¿...?"                  # pregunta libre
  python -m src.leer_registros_rag --informe                     # estadísticas y docs/resultados_bloque28.md

Cada consulta se AGREGA a registros_latencia_costo.jsonl (excluido de Git); nunca se borran líneas.
"""
from __future__ import annotations

import argparse
import sys
import time

from src.rag.configuracion import CONFIG_BLOQUE26_MD, obtener_modelo_chat
from src.rag.costos import cargar_tarifas
from src.rag.embeddings import EmbeddingsConReintentos, crear_embeddings_gemini
from src.rag.errores import ErrorRAG
from src.rag.evaluacion_bloque27 import ARCHIVO_CASOS, cargar_dataset
from src.rag.expansion import expandir_hasta_k
from src.rag.generador import crear_modelo_chat, recuperar
from src.rag.hibrido import CANDIDATOS_POR_DEFECTO
from src.rag.indexador import cargar_indice
from src.rag.observabilidad import (
    ARCHIVO_REGISTROS, ContextoConsulta, consultar_instrumentado, guardar_registro, nuevo_id_ejecucion, relanzar,
)
from src.rag.recuperador import buscar_por_vector_con_score

CASOS_POR_DEFECTO = ("c01-backoff", "c07-aprobacion", "c04-tarifa")


def preguntas_de(opciones) -> list[tuple[str, str]]:
    if opciones.pregunta:
        return [("libre", p) for p in opciones.pregunta]
    casos = {c["id"]: c for c in cargar_dataset(ARCHIVO_CASOS)["casos"]}
    faltan = [i for i in opciones.casos if i not in casos]
    if faltan:
        raise ErrorRAG(f"Casos inexistentes en el dataset del Bloque 27: {faltan}")
    return [(i, casos[i]["pregunta"]) for i in opciones.casos]


def comparar_ruta(almacen, embeddings, preguntas, k: int) -> bool:
    """Ruta anterior (similarity_search_with_score) frente a la instrumentada (embed_query + búsqueda por vector)."""
    iguales = True
    for caso, pregunta in preguntas:
        antes = embeddings.llamadas_consulta
        anterior = recuperar(almacen, pregunta, k, "vectorial", True)
        llamadas_anterior = embeddings.llamadas_consulta - antes
        antes = embeddings.llamadas_consulta
        vector = embeddings.embed_query(pregunta)
        pares = buscar_por_vector_con_score(almacen, vector, max(k, CANDIDATOS_POR_DEFECTO))
        nuevo = expandir_hasta_k(almacen, [d for d, _ in pares], k)
        llamadas_nuevo = embeddings.llamadas_consulta - antes
        ids_a = [r.documento.metadata.get("chunk_recuperado") for r in anterior]
        ids_n = [d.metadata.get("chunk_recuperado") for _, d in nuevo]
        dist_a = [round(r.puntaje, 6) for r in anterior]
        dist_n = [round(float(pares[p][1]), 6) for p, _ in nuevo]
        textos_iguales = [r.documento.page_content for r in anterior] == [d.page_content for _, d in nuevo]
        igual = ids_a == ids_n and dist_a == dist_n and textos_iguales
        iguales &= igual
        print(f"{caso}: {'IGUAL' if igual else 'DISTINTO'} | unidades={ids_n} | distancias anterior={dist_a} "
              f"nueva={dist_n} | embed_query: anterior={llamadas_anterior}, instrumentada={llamadas_nuevo}")
    return iguales


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--casos", nargs="+", default=list(CASOS_POR_DEFECTO), help="IDs del dataset del Bloque 27")
    parser.add_argument("--pregunta", action="append", help="Pregunta libre (repetible); reemplaza --casos")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--sin-expandir", action="store_true")
    parser.add_argument("--sin-generar", action="store_true", help="Mide solo recuperación y prompt")
    parser.add_argument("--comparar-ruta", action="store_true", help="Compara la ruta anterior y la instrumentada (sin generar)")
    parser.add_argument("--registro", default=str(ARCHIVO_REGISTROS))
    opciones = parser.parse_args(argv)
    try:
        preguntas = preguntas_de(opciones)
        config = CONFIG_BLOQUE26_MD
        inicio = time.perf_counter()
        embeddings = EmbeddingsConReintentos(crear_embeddings_gemini(config.modelo_embeddings))
        almacen = cargar_indice(config, embeddings)
        carga_ms = (time.perf_counter() - inicio) * 1000
        if opciones.comparar_ruta:
            return 0 if comparar_ruta(almacen, embeddings, preguntas, opciones.k) else 1
        inicio = time.perf_counter()
        modelo = None if opciones.sin_generar else crear_modelo_chat()
        crear_modelo_ms = (time.perf_counter() - inicio) * 1000
        contexto = ContextoConsulta("markdown", config.nombre_coleccion, config.modelo_embeddings,
                                    obtener_modelo_chat(), "real", nuevo_id_ejecucion())
        tarifas = cargar_tarifas()
        print(f"Ejecución {contexto.id_ejecucion} | índice {config.nombre_coleccion} | modelo {contexto.modelo_generacion} | "
              f"carga del índice {carga_ms:.1f} ms | creación del modelo {crear_modelo_ms:.1f} ms (fuera del total por consulta)")
        for caso, pregunta in preguntas:
            registro = consultar_instrumentado(almacen, embeddings, modelo, pregunta, contexto, tarifas, k=opciones.k,
                                               expandir=not opciones.sin_expandir, generar=not opciones.sin_generar)
            registro["caso"] = caso
            registro["preparacion_ejecucion_ms"] = {"carga_indice": round(carga_ms, 3), "crear_modelo": round(crear_modelo_ms, 3)}
            guardar_registro(registro, opciones.registro)
            t, g = registro["tiempos_ms"], (registro.get("tokens") or {}).get("generacion", {})
            costo = (registro.get("costo_usd") or {}).get("total_conocido_usd")
            print(f"{caso:<16} k={opciones.k} estado={registro['estado']} total={registro['tiempo_total_ms']} ms | "
                  f"embed={t.get('embed_query')} busq={t.get('busqueda_vectorial')} exp={t.get('expansion_contexto')} "
                  f"prompt={t.get('construccion_prompt')} gen={t.get('generacion')} sobrecarga={registro['sobrecarga_ms']} | "
                  f"tokens in={g.get('entrada')} out={g.get('salida')} total={g.get('total')} razonamiento={g.get('razonamiento')} | "
                  f"secciones={registro['recuperacion']['secciones_unicas']} contexto={registro['caracteres_contexto']} car. | "
                  f"costo_gen={costo}")
            relanzar(registro)  # si hubo error ya quedó registrado; no se oculta
        print(f"embed_documents={embeddings.llamadas_documentos} (no reindexa), embed_query={embeddings.llamadas_consulta}")
        return 0
    except ErrorRAG as error:
        print(f"Error ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
