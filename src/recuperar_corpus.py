"""Bloque 26: recuperación semántica sobre la documentación del proyecto y respuesta con citas.

Configuración predeterminada (consolidada tras la optimización del escenario B):
  índice por secciones Markdown (corpus_proyecto_bloque24_md) + búsqueda vectorial
  + expansión de cada chunk a su sección (small-to-big).

Requisito, una sola vez (242 embeddings):
  python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md

Ejemplos (desde la raíz del repositorio):
  python -m src.recuperar_corpus "¿Qué pasa si Gemini no responde?"
  python -m src.recuperar_corpus --escenarios                         # escenarios A, B y C
  python -m src.recuperar_corpus "..." --sin-generar                  # solo recuperación + prompt
  python -m src.recuperar_corpus "..." --k 5 --max-contexto 2500      # límite de contexto (sin recortar unidades)
  python -m src.recuperar_corpus "..." --modo hibrido                 # vectorial + BM25 con RRF
  python -m src.recuperar_corpus "..." --sin-expandir                 # chunks sin expandir
  python -m src.recuperar_corpus "..." --indice base --sin-expandir   # comportamiento original del Bloque 26

Puntajes: en modo vectorial es la DISTANCIA coseno (menor = más parecido); en modo híbrido es
el puntaje RRF (mayor = mejor). Ninguno es un porcentaje.
"""
from __future__ import annotations

import argparse
import sys

from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE26_MD, K_POR_DEFECTO
from src.rag.embeddings import EmbeddingsConReintentos, crear_embeddings_gemini
from src.rag.errores import ErrorRAG
from src.rag.expansion import MAX_CARACTERES_SECCION
from src.rag.generador import (
    MODOS, RESPUESTA_SIN_CONTEXTO, calcular_metricas, crear_modelo_chat, generar, preparar_contexto,
)
from src.rag.indexador import cargar_indice
from src.rag.prompts import construir_prompt
from src.rag.recuperador import buscar, crear_retriever

INDICES = {"markdown": CONFIG_BLOQUE26_MD, "base": CONFIG_BLOQUE24}

ESCENARIOS = {
    "A (reintentos, con otras palabras)": "¿Qué hace el programa cuando el servidor de Google tarda en contestar o devuelve demasiadas peticiones?",
    "B (agentes y aprobación)": "¿Qué herramienta del agente necesita que una persona la autorice antes de ejecutarse?",
    "C (fuera del corpus)": "¿Cuál es el horario de atención de la biblioteca municipal de Valparaíso?",
}


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pregunta", nargs="?")
    parser.add_argument("--k", type=int, default=K_POR_DEFECTO, help="Unidades de contexto (defecto 3)")
    parser.add_argument("--sin-generar", action="store_true", help="No invoca el modelo de chat")
    parser.add_argument("--escenarios", action="store_true", help="Ejecuta los escenarios A, B y C")
    parser.add_argument("--indice", choices=tuple(INDICES), default="markdown",
                        help="markdown (defecto) = corpus_proyecto_bloque24_md; base = corpus_proyecto_bloque24")
    parser.add_argument("--modo", choices=MODOS, default="vectorial", help="vectorial (defecto) o hibrido")
    expansion = parser.add_mutually_exclusive_group()
    expansion.add_argument("--expandir", dest="expandir", action="store_true", default=True,
                           help="Expande cada chunk a su sección (defecto; se acepta por compatibilidad)")
    expansion.add_argument("--sin-expandir", dest="expandir", action="store_false",
                           help="Usa los chunks tal como se recuperan")
    parser.add_argument("--max-seccion", type=int, default=MAX_CARACTERES_SECCION,
                        help="Tamaño máximo de una sección expandida; si se excede, se usa una ventana de vecinos")
    parser.add_argument("--max-contexto", type=int, default=None,
                        help="Límite de caracteres del contexto; se omiten unidades completas, nunca se recortan")
    parser.add_argument("--coleccion", help="Colección alternativa (avanzado)")
    parser.add_argument("--chunk-size", type=int, help="Debe coincidir con el usado al indexar")
    parser.add_argument("--chunk-overlap", type=int, help="Debe coincidir con el usado al indexar")
    return parser


def resolver_configuracion(opciones):
    cambios = {k: v for k, v in {"nombre_coleccion": opciones.coleccion, "chunk_size": opciones.chunk_size,
                                 "chunk_overlap": opciones.chunk_overlap}.items() if v is not None}
    base = INDICES[opciones.indice]
    return base.con(**cambios) if cambios else base


def consultar(almacen, modelo, pregunta: str, opciones, generar_respuesta: bool) -> dict:
    print("=" * 80)
    print("Pregunta:", pregunta)
    incluidos, omitidos, contexto, citas = preparar_contexto(
        almacen, pregunta, opciones.k, opciones.modo, opciones.expandir,
        max_contexto=opciones.max_contexto, max_seccion=opciones.max_seccion)
    print(f"\nRecuperados (k={opciones.k}, modo={opciones.modo}, expandir={opciones.expandir}):")
    for i, r in enumerate(incluidos, start=1):
        m = r.documento.metadata
        extra = (f" {m.get('expansion', 'sin expansión')}={m.get('seccion')!r} "
                 f"chunks={len(m.get('chunk_ids_expandidos', [1]))}") if opciones.expandir else ""
        print(f"  [{i}] {r.tipo_puntaje}={r.puntaje:.4f}  {m.get('fuente')}  chunk={m.get('chunk_index')}{extra}")
    for r in omitidos:
        print(f"  (omitido por --max-contexto) {r.documento.metadata.get('fuente')} chunk={r.documento.metadata.get('chunk_index')}")
    print("\nContexto:\n" + (contexto or "(vacío)"))
    print("\nCitas:", citas)
    respuesta = ""
    if not incluidos:
        respuesta = RESPUESTA_SIN_CONTEXTO
        print("\nRespuesta:", respuesta)
    elif not generar_respuesta:
        print("\nPrompt construido (no se invocó el modelo):")
        for mensaje in construir_prompt(pregunta, contexto).to_messages():
            print(f"--- {mensaje.type} ---\n{mensaje.content}")
    else:
        respuesta = generar(modelo, construir_prompt(pregunta, contexto))
        print("\nRespuesta del modelo:\n" + respuesta)
    metricas = calcular_metricas(incluidos, omitidos, contexto, citas, respuesta)
    print("\nMétricas:", metricas)
    return metricas


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    opciones = parser.parse_args(argv)
    if not opciones.pregunta and not opciones.escenarios:
        parser.error("Indica una pregunta o --escenarios.")
    try:
        config = resolver_configuracion(opciones)
        embeddings = EmbeddingsConReintentos(crear_embeddings_gemini(config.modelo_embeddings))
        almacen = cargar_indice(config, embeddings)
        print(f"Índice cargado: {config.nombre_coleccion} con {almacen._collection.count()} chunks "
              f"({config.estrategia} {config.chunk_size}/{config.chunk_overlap}); modo={opciones.modo}, "
              f"expandir={opciones.expandir}, max_contexto={opciones.max_contexto}.")
        modelo = None if opciones.sin_generar else crear_modelo_chat()
        preguntas = list(ESCENARIOS.items()) if opciones.escenarios else [("consulta", opciones.pregunta)]
        for nombre, pregunta in preguntas:
            print(f"\n### Escenario {nombre}")
            consultar(almacen, modelo, pregunta, opciones, not opciones.sin_generar)
        # Las otras dos interfaces de LangChain sobre la primera pregunta (chunks sin expandir).
        primera = preguntas[0][1]
        print("\nsimilarity_search():", [d.metadata.get("fuente") for d in buscar(almacen, primera, opciones.k)])
        print("as_retriever().invoke():",
              [d.metadata.get("fuente") for d in crear_retriever(almacen, opciones.k).invoke(primera)])
        print(f"\nUso de embeddings: embed_documents={embeddings.llamadas_documentos} (debe ser 0, no reindexa), "
              f"embed_query={embeddings.llamadas_consulta}.")
        return 0
    except ErrorRAG as error:
        print(f"Error ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
