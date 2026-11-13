"""Bloques 24 y 25: comparar chunking, indexar en Chroma y verificar persistencia.

Desde la raíz del repositorio:
  python -m src.indexar_corpus --bloque 24 --comparar        # sin API: compara estrategias
  python -m src.indexar_corpus --bloque 24                   # indexa con embeddings reales de Gemini
  python -m src.indexar_corpus --bloque 24 --solo-verificar  # sin API: recuento desde otro proceso
  python -m src.indexar_corpus --bloque 25                   # réplica en vectorstore_ejemplo/
  python -m src.indexar_corpus --bloque 24 --reconstruir     # borra SOLO esa colección y reindexa
  python -m src.indexar_corpus --bloque 24 --estrategia markdown --coleccion corpus_proyecto_bloque24_md
  python -m src.indexar_corpus --bloque 24 --plan            # sin API: chunks nuevos y huérfanos tras editar documentos
  python -m src.indexar_corpus --bloque 24 --podar-huerfanos # actualiza solo los chunks afectados y elimina los obsoletos
"""
from __future__ import annotations

import argparse
import json
import sys

from src.rag.chunking import comparar_estrategias, dividir_documentos, estadisticas_chunks
from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE25, ESTRATEGIAS
from src.rag.corpus import MANIFIESTO_BLOQUE24, MANIFIESTO_BLOQUE25, cargar_documentos
from src.rag.embeddings import EmbeddingsConReintentos, crear_embeddings_gemini
from src.rag.errores import ErrorRAG
from src.rag.indexador import contar_en_otro_proceso, indexar, planificar_indexacion, verificar_persistencia

BLOQUES = {24: (CONFIG_BLOQUE24, MANIFIESTO_BLOQUE24), 25: (CONFIG_BLOQUE25, MANIFIESTO_BLOQUE25)}


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bloque", type=int, choices=sorted(BLOQUES), default=24)
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--chunk-overlap", type=int)
    parser.add_argument("--estrategia", choices=ESTRATEGIAS)
    parser.add_argument("--coleccion", help="Nombre de colección alternativo (p. ej. para experimentar con otro chunk_size)")
    parser.add_argument("--comparar", action="store_true", help="Solo compara estrategias de chunking (sin API)")
    parser.add_argument("--solo-verificar", action="store_true", help="Solo verifica el índice persistido (sin API)")
    parser.add_argument("--reconstruir", action="store_true", help="Borra la colección indicada antes de indexar")
    parser.add_argument("--plan", action="store_true",
                        help="Muestra chunks nuevos y huérfanos sin calcular embeddings ni escribir (sin API)")
    parser.add_argument("--podar-huerfanos", action="store_true",
                        help="Elimina de ESTA colección solo los chunks que ya no existen en el corpus")
    parser.add_argument("--lote", type=int, default=20, help="Textos por solicitud de embeddings (defecto 20)")
    parser.add_argument("--pausa", type=float, default=15.0,
                        help="Segundos entre lotes para respetar la cuota por minuto (defecto 15)")
    return parser


def resolver_configuracion(opciones):
    config, manifiesto = BLOQUES[opciones.bloque]
    cambios = {k: v for k, v in {"chunk_size": opciones.chunk_size, "chunk_overlap": opciones.chunk_overlap,
                                 "estrategia": opciones.estrategia,
                                 "nombre_coleccion": opciones.coleccion}.items() if v is not None}
    return (config.con(**cambios) if cambios else config), manifiesto


def mostrar_comparacion(documentos, config) -> None:
    comparacion = comparar_estrategias(documentos, config.chunk_size, config.chunk_overlap, estrategias=ESTRATEGIAS)
    print(f"Comparación con chunk_size={config.chunk_size}, chunk_overlap={config.chunk_overlap}:")
    for estrategia, datos in comparacion.items():
        print(f"\n[{estrategia}] chunks={datos['cantidad']} min={datos['minimo']} max={datos['maximo']} "
              f"promedio={datos['promedio']} cortes_a_mitad_de_palabra={datos['cortes_a_mitad_de_palabra']} "
              f"menores_de_40={datos['menores_de_40']} solo_encabezado={datos['solo_encabezado']} "
              f"empiezan_con_punto={datos['empiezan_con_punto']}")
        for i, ejemplo in enumerate(datos["ejemplos"], start=1):
            print(f"  ejemplo {i}: {ejemplo!r}")


def verificar(config, esperado: int | None) -> bool:
    local = verificar_persistencia(config, esperado)
    print("Verificación en este proceso:", json.dumps(local, ensure_ascii=False))
    remoto = contar_en_otro_proceso(config)
    coincide = remoto == local["conteo"] and (esperado is None or remoto == esperado)
    print(f"Recuento desde otro proceso: {remoto} -> {'consistente' if coincide else 'INCONSISTENTE'}")
    return local["consistente"] and coincide


def main(argv: list[str] | None = None) -> int:
    opciones = construir_parser().parse_args(argv)
    try:
        config, manifiesto = resolver_configuracion(opciones)
        if opciones.solo_verificar:
            return 0 if verificar(config, None) else 1

        documentos = cargar_documentos(manifiesto)
        print(f"Bloque {opciones.bloque}: {len(documentos)} documentos cargados:")
        for d in documentos:
            print(f"  - {d.metadata['fuente']} ({len(d.page_content)} caracteres, bloque={d.metadata.get('bloque', 'sin asignar')})")
        if opciones.comparar:
            mostrar_comparacion(documentos, config)
            return 0

        chunks = dividir_documentos(documentos, config.estrategia, config.chunk_size, config.chunk_overlap)
        print(f"Chunking {config.estrategia} ({config.chunk_size}/{config.chunk_overlap}):",
              json.dumps(estadisticas_chunks(chunks)))
        if opciones.plan:
            plan = planificar_indexacion(chunks, config)
            print(f"Plan para {config.nombre_coleccion}: existe={plan['coleccion_existe']}, "
                  f"nuevos={len(plan['nuevos'])} (fuentes: {plan['fuentes_con_nuevos']}), "
                  f"ya_existentes={plan['ya_existentes']}, huerfanos={len(plan['huerfanos'])}")
            for chunk_id in plan["huerfanos"]:
                print(f"  huérfano: {chunk_id}")
            return 0
        embeddings = EmbeddingsConReintentos(crear_embeddings_gemini(config.modelo_embeddings),
                                             intentos=6, espera_base=10, espera_maxima=60)
        resultado = indexar(chunks, config, embeddings, reconstruir=opciones.reconstruir,
                            tamano_lote=opciones.lote, pausa_entre_lotes=opciones.pausa,
                            podar_huerfanos=opciones.podar_huerfanos)
        print("Indexación:", json.dumps(resultado.__dict__, ensure_ascii=False))
        print(f"Embeddings calculados en esta ejecución: {embeddings.textos_embebidos} textos "
              f"en {embeddings.llamadas_documentos} llamadas (modelo {config.modelo_embeddings}).")
        if resultado.huerfanos and not resultado.podados:
            print(f"Aviso: {len(resultado.huerfanos)} chunks del índice ya no están en el corpus. "
                  "Usa --podar-huerfanos para eliminar solo esos chunks.")
        return 0 if verificar(config, len(chunks) + len(resultado.huerfanos) - resultado.podados) else 1
    except ErrorRAG as error:
        print(f"Error ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
