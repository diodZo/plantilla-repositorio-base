"""Bloque 27: evaluación cuantitativa de la recuperación del RAG.

RUTA HEREDADA para la generación opcional (no recomendada desde el Gate 2): usa el prompt del
Bloque 26 sin filtro de inyección. La evaluación de recuperación no genera respuestas.

Desde la raíz del repositorio:
  python -m src.evaluar_bloque27 --etiquetar         # una sola vez: deriva IDs de los pasajes y congela (sin API)
  python -m src.evaluar_bloque27                     # evaluación real: 1 embed_query por pregunta e índice
  python -m src.evaluar_bloque27 --incluir-hibrido   # agrega BM25+RRF (sin llamadas extra)
  python -m src.evaluar_bloque27 --abstencion        # además genera respuestas para los casos sin respuesta
  python -m src.evaluar_bloque27 --solo-informe      # regenera el Markdown desde el historial JSON (sin API)

Cada ejecución se AGREGA a docs/resultados_evaluacion_bloque27.json (no se borran las anteriores)
y regenera docs/resultados_evaluacion_bloque27.md. No calcula embeddings de documentos ni reindexa.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.rag.chunking import dividir_documentos
from src.rag.configuracion import RAIZ_REPO, obtener_modelo_chat
from src.rag.corpus import MANIFIESTO_BLOQUE24, cargar_documentos
from src.rag.embeddings import EmbeddingsConReintentos, crear_embeddings_gemini
from src.rag.errores import ErrorRAG
from src.rag.evaluacion_bloque27 import (
    ARCHIVO_CASOS, ARCHIVO_RESULTADOS_JSON, ARCHIVO_RESULTADOS_MD, CANDIDATOS, CONFIGURACIONES,
    CONFIGURACIONES_HIBRIDAS, INDICES, KS_POR_DEFECTO, agregar, ahora_utc, cargar_dataset, comparar_ejecuciones,
    construir_rankings, describir_indice, detectar_abstencion, etiquetar, evaluar_caso, guardar_ejecucion,
    huella_etiquetas, peores_casos,
)
from src.rag.expansion import MAX_CARACTERES_SECCION
from src.rag.indexador import _cliente, cargar_indice, validar_metadata_coleccion
from src.rag.lexico import IndiceBM25

LIMITACIONES = [
    "Dataset pequeño (10 casos con respuesta y 2 sin respuesta): un caso equivale a 0,1 en Recall/Hit promedio.",
    "Etiquetado hecho por el desarrollador del sistema, no por evaluadores externos independientes.",
    "Mide la recuperación, no la calidad de la respuesta generada.",
    "Las métricas de sección (nivel B) no son comparables uno a uno con las de chunk (nivel A): las unidades son más grandes.",
    "Sin umbral de distancia: los casos sin respuesta siempre reciben contexto; la abstención depende del modelo generativo.",
]


def etiquetar_y_congelar() -> int:
    datos = json.loads(ARCHIVO_CASOS.read_text(encoding="utf-8"))
    documentos = cargar_documentos(MANIFIESTO_BLOQUE24)
    textos = {d.metadata["fuente"]: d.page_content for d in documentos}
    chunks_por_indice = {}
    for nombre, config in INDICES.items():
        # Se valida que la colección persistida use la misma configuración que el chunking local.
        coleccion = _cliente(Path(config.directorio)).get_collection(config.nombre_coleccion)
        validar_metadata_coleccion(coleccion.metadata, config)
        chunks = dividir_documentos(documentos, config.estrategia, config.chunk_size, config.chunk_overlap)
        presentes = set(coleccion.get(ids=[c.id for c in chunks], include=[])["ids"])
        faltan = [c.id for c in chunks if c.id not in presentes]
        if faltan:
            raise ErrorRAG(f"{len(faltan)} IDs del chunking local no están en {config.nombre_coleccion}; "
                           "revisa la sincronización con `python -m src.indexar_corpus --plan` antes de etiquetar.")
        chunks_por_indice[nombre] = chunks
    etiquetar(datos, chunks_por_indice, textos, ahora_utc())
    ARCHIVO_CASOS.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Dataset congelado ({datos['congelado']}), huella {datos['huella_etiquetas'][:12]}…")
    for c in datos["casos"]:
        r = c["relevantes"]
        print(f"  {c['id']:<22} base={len(r['base']['chunks'])} chunks | markdown={len(r['markdown']['chunks'])} "
              f"chunks, {len(r['markdown'].get('secciones', []))} secciones")
    return 0


def evaluar(opciones) -> dict:
    dataset = cargar_dataset(ARCHIVO_CASOS)
    casos = dataset["casos"]
    configuraciones = CONFIGURACIONES + (CONFIGURACIONES_HIBRIDAS if opciones.incluir_hibrido else ())
    embeddings = EmbeddingsConReintentos(crear_embeddings_gemini())
    almacenes = {n: cargar_indice(c, embeddings) for n, c in INDICES.items()}
    bm25 = {n: IndiceBM25.desde_almacen(a) for n, a in almacenes.items()} if opciones.incluir_hibrido else {}
    metodos = {c.metodo for c in configuraciones}
    por_caso, distancias = {}, {}
    for caso in casos:
        rankings, distancias[caso["id"]] = construir_rankings(almacenes, caso["pregunta"], metodos, bm25, opciones.candidatos)
        por_caso[caso["id"]] = evaluar_caso(caso, rankings, almacenes, configuraciones, KS_POR_DEFECTO, opciones.max_seccion)
        print(f"  {caso['id']}: listo")
    generaciones = 0
    abstencion = {}
    if opciones.abstencion:
        from src.rag.generador import crear_modelo_chat, generar, preparar_contexto
        from src.rag.prompts import construir_prompt
        modelo = crear_modelo_chat()
        for caso in (c for c in casos if c["sin_respuesta"]):
            incluidos, _, contexto, citas = preparar_contexto(almacenes["markdown"], caso["pregunta"], 3, "vectorial", True)
            respuesta = generar(modelo, construir_prompt(caso["pregunta"], contexto))
            generaciones += 1
            abstencion[caso["id"]] = {"configuracion": "markdown_expandido, k=3 (predeterminada de la CLI)",
                                      "respuesta": respuesta, "se_abstuvo": detectar_abstencion(respuesta),
                                      "fuentes_en_contexto": sorted(set(citas.values()))}
    sin_respuesta = {
        c["id"]: {"distancia_top1": {n: distancias[c["id"]][n][0] for n in INDICES},
                  "abstencion_generador": abstencion.get(c["id"])}
        for c in casos if c["sin_respuesta"]
    }
    respondibles_top1 = {n: [distancias[c["id"]][n][0] for c in casos if not c["sin_respuesta"]] for n in INDICES}
    agregados = agregar(por_caso, casos, configuraciones)
    return {
        "id_ejecucion": ahora_utc(),
        "fecha_utc": ahora_utc(),
        "dataset": {"ruta": ARCHIVO_CASOS.relative_to(RAIZ_REPO).as_posix(), "congelado": dataset["congelado"],
                    "huella_etiquetas": huella_etiquetas(casos), "casos": len(casos),
                    "con_respuesta": sum(not c["sin_respuesta"] for c in casos),
                    "sin_respuesta": sum(c["sin_respuesta"] for c in casos)},
        "indices": {n: describir_indice(a, INDICES[n]) for n, a in almacenes.items()},
        "parametros": {"ks": list(KS_POR_DEFECTO), "candidatos": opciones.candidatos,
                       "max_seccion": opciones.max_seccion, "incluir_hibrido": opciones.incluir_hibrido,
                       "modelo_chat": obtener_modelo_chat() if opciones.abstencion else None},
        "configuraciones": {c.nombre: {"indice": c.indice, "nivel": c.nivel, "metodo": c.metodo,
                                       "expansion": c.expansion} for c in configuraciones},
        "llamadas_api": {"embed_query": embeddings.llamadas_consulta, "embed_documents": embeddings.llamadas_documentos,
                         "generaciones": generaciones},
        "agregados": agregados,
        "por_caso": por_caso,
        "distancias_top5": distancias,
        "sin_respuesta": sin_respuesta,
        "distancia_top1_respondibles": {n: {"min": min(v), "max": max(v)} for n, v in respondibles_top1.items()},
        "peores_casos": {c.nombre: {str(k): peores_casos(por_caso, casos, c.nombre, k) for k in KS_POR_DEFECTO}
                         for c in configuraciones},
        "limitaciones": LIMITACIONES,
    }


def _f(valor) -> str:
    return "—" if valor is None else f"{valor:.3f}"


def escribir_informe(historial: dict, ruta: Path = ARCHIVO_RESULTADOS_MD) -> None:
    """Regenera el Markdown desde el historial JSON (todas las ejecuciones se conservan en el JSON)."""
    ejecuciones = historial["ejecuciones"]
    if not ejecuciones:
        raise ValueError("No hay ejecuciones registradas.")
    ultima = ejecuciones[-1]
    lineas = [
        "# Resultados de evaluación — Bloque 27",
        "",
        "> Archivo generado por `python -m src.evaluar_bloque27` a partir de "
        "`docs/resultados_evaluacion_bloque27.json`, que conserva **todas** las ejecuciones. "
        "El análisis está en `docs/README-bloque27.md` y `docs/ensayo-bloque27.md`.",
        "",
        "## Historial de ejecuciones",
        "",
        "| Ejecución (UTC) | Dataset (huella) | Configuraciones | embed_query | embed_documents | Generaciones |",
        "|---|---|---|---|---|---|",
    ]
    for e in ejecuciones:
        lineas.append(f"| {e['fecha_utc']} | {e['dataset']['huella_etiquetas'][:12]} | {', '.join(e['configuraciones'])} | "
                      f"{e['llamadas_api']['embed_query']} | {e['llamadas_api']['embed_documents']} | "
                      f"{e['llamadas_api']['generaciones']} |")
    if len(ejecuciones) >= 2:
        comparacion = comparar_ejecuciones(ejecuciones[-2], ultima)
        lineas += ["", f"**Estabilidad (últimas dos ejecuciones):** "
                   f"{'rankings y promedios idénticos' if comparacion['identicas'] else 'hay diferencias'} — "
                   f"{len(comparacion['rankings_distintos'])} rankings distintos, "
                   f"{len(comparacion['promedios_distintos'])} promedios distintos."]
        for d in comparacion["rankings_distintos"][:20]:
            lineas.append(f"- Ranking distinto: {d['caso']} / {d['configuracion']} / k={d['k']}")
    d = ultima["dataset"]
    lineas += ["", f"## Última ejecución: {ultima['fecha_utc']}", "",
               f"- Dataset: `{d['ruta']}` (congelado {d['congelado']}, huella `{d['huella_etiquetas'][:12]}`): "
               f"{d['casos']} casos, {d['con_respuesta']} con respuesta, {d['sin_respuesta']} sin respuesta.",
               f"- Parámetros: k = {ultima['parametros']['ks']}, candidatos = {ultima['parametros']['candidatos']}, "
               f"máx. sección = {ultima['parametros']['max_seccion']} caracteres.",
               "", "### Índices (leídos de Chroma)", "",
               "| Índice | Colección | Modelo de embeddings | Estrategia | chunk_size/overlap | Documentos | Chunks | Secciones |",
               "|---|---|---|---|---|---|---|---|"]
    for n, i in ultima["indices"].items():
        lineas.append(f"| {n} | `{i['coleccion']}` | `{i['modelo_embeddings']}` | {i['estrategia']} | "
                      f"{i['chunk_size']}/{i['chunk_overlap']} | {i['documentos']} | {i['chunks']} | {i['secciones'] or '—'} |")
    lineas += ["", "### Promedios (solo casos con respuesta)", "",
               "| Configuración | Nivel | k | Precision | Recall | F1 | Hit | Caracteres de contexto | Chunks en contexto | Excluidos (sin respuesta) |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for nombre, por_k in ultima["agregados"].items():
        nivel = ultima["configuraciones"][nombre]["nivel"]
        for k, m in por_k.items():
            lineas.append(f"| {nombre} | {nivel} | {k} | {_f(m['precision']['media'])} | {_f(m['recall']['media'])} | "
                          f"{_f(m['f1']['media'])} | {_f(m['hit']['media'])} | {m['caracteres_contexto']['media']:.0f} | "
                          f"{m['chunks_en_contexto']['media']:.1f} | {m['casos_sin_respuesta_excluidos']} |")
    lineas += ["", "### Métricas por caso (Precision / Recall / F1 / Hit)", ""]
    nombres = list(ultima["agregados"])
    lineas += ["| Caso | " + " | ".join(f"{n} k={k}" for n in nombres for k in ultima["parametros"]["ks"]) + " |",
               "|---|" + "---|" * (len(nombres) * len(ultima["parametros"]["ks"]))]
    for caso_id, por_cfg in ultima["por_caso"].items():
        celdas = []
        for n in nombres:
            for k in ultima["parametros"]["ks"]:
                m = por_cfg[n][str(k)]
                celdas.append(f"{_f(m['precision'])} / {_f(m['recall'])} / {_f(m['f1'])} / {_f(m['hit'])}")
        lineas.append(f"| {caso_id} | " + " | ".join(celdas) + " |")
    lineas += ["", "### Peores casos (menor recall y luego menor F1)", ""]
    for nombre, por_k in ultima["peores_casos"].items():
        for k, filas in por_k.items():
            lineas.append(f"- **{nombre}, k={k}:** " + "; ".join(
                f"{f['id']} (R={_f(f['recall'])}, F1={_f(f['f1'])})" for f in filas))
    lineas += ["", "### Casos sin respuesta (se excluyen del recall)", "",
               "| Caso | Distancia top‑1 (base) | Distancia top‑1 (markdown) | Abstención del generador |", "|---|---|---|---|"]
    for caso_id, info in ultima["sin_respuesta"].items():
        # La abstención solo se mide con --abstencion: se muestra la medición más reciente del historial.
        medida = next(((e["fecha_utc"], e["sin_respuesta"][caso_id]["abstencion_generador"]) for e in reversed(ejecuciones)
                       if e["sin_respuesta"].get(caso_id, {}).get("abstencion_generador")), None)
        if medida is None:
            texto_ab = "no medida"
        else:
            fecha, ab = medida
            texto_ab = (f"{'sí' if ab['se_abstuvo'] else '**no**'} (medida {fecha}): "
                        f"«{ab['respuesta'][:120]}»")
        lineas.append(f"| {caso_id} | {info['distancia_top1']['base']:.4f} | {info['distancia_top1']['markdown']:.4f} | {texto_ab} |")
    rango = ultima["distancia_top1_respondibles"]
    lineas += ["", "Distancia top‑1 de los casos con respuesta: " + "; ".join(
        f"{n} {v['min']:.4f}–{v['max']:.4f}" for n, v in rango.items()) + ".",
        "", "### Limitaciones", ""] + [f"- {l}" for l in ultima["limitaciones"]]
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--etiquetar", action="store_true", help="Deriva los IDs relevantes y congela el dataset (sin API)")
    parser.add_argument("--incluir-hibrido", action="store_true")
    parser.add_argument("--abstencion", action="store_true", help="Genera respuestas para los casos sin respuesta")
    parser.add_argument("--solo-informe", action="store_true", help="Regenera el Markdown sin ejecutar consultas")
    parser.add_argument("--sin-guardar", action="store_true", help="No agrega la ejecución al historial")
    parser.add_argument("--candidatos", type=int, default=CANDIDATOS)
    parser.add_argument("--max-seccion", type=int, default=MAX_CARACTERES_SECCION)
    opciones = parser.parse_args(argv)
    try:
        if opciones.etiquetar:
            return etiquetar_y_congelar()
        if opciones.solo_informe:
            escribir_informe(json.loads(ARCHIVO_RESULTADOS_JSON.read_text(encoding="utf-8")))
            print(f"Informe regenerado: {ARCHIVO_RESULTADOS_MD.relative_to(RAIZ_REPO)}")
            return 0
        ejecucion = evaluar(opciones)
        for nombre, por_k in ejecucion["agregados"].items():
            for k, m in por_k.items():
                print(f"{nombre:<28} k={k}  P={_f(m['precision']['media'])} R={_f(m['recall']['media'])} "
                      f"F1={_f(m['f1']['media'])} Hit={_f(m['hit']['media'])} "
                      f"contexto≈{m['caracteres_contexto']['media']:.0f} car.")
        print("Llamadas a la API:", ejecucion["llamadas_api"])
        if not opciones.sin_guardar:
            historial = guardar_ejecucion(ejecucion)
            escribir_informe(historial)
            print(f"Guardado en {ARCHIVO_RESULTADOS_JSON.relative_to(RAIZ_REPO)} ({len(historial['ejecuciones'])} ejecuciones) "
                  f"y {ARCHIVO_RESULTADOS_MD.relative_to(RAIZ_REPO)}")
        return 0
    except ErrorRAG as error:
        print(f"Error ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
