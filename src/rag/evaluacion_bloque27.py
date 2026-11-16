"""Bloque 27: evaluación cuantitativa de la recuperación (Precision@k, Recall@k, F1, Hit@k).

Dos niveles, que nunca se mezclan:
- Nivel A (chunks): los primeros k chunks del ranking contra los IDs de chunks relevantes.
- Nivel B (secciones): las k unidades de contexto que llegan al generador tras la expansión
  small-to-big, identificadas por sección (`documento_id#ruta`) y sin contar dos veces una
  sección alcanzada desde chunks distintos.

Por cada índice se hace UNA consulta vectorial por pregunta (una `embed_query`) con profundidad
`candidatos`. De ese mismo ranking salen k=3, k=5, el nivel A y el nivel B. Nunca se calculan
embeddings de documentos ni se reindexa.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from src.rag.configuracion import CONFIG_BLOQUE24, CONFIG_BLOQUE26_MD, RAIZ_REPO, ConfiguracionIndice
from src.rag.errores import ErrorRAG
from src.rag.etiquetado import chunks_relevantes, id_seccion, pasaje_existe_en_fuente, secciones_de
from src.rag.expansion import MAX_CARACTERES_SECCION, expandir_hasta_k
from src.rag.hibrido import fusionar_rrf
from src.rag.lexico import IndiceBM25, normalizar
from src.rag.metricas import metricas_en_k, promedio
from src.rag.recuperador import buscar_con_score, formatear_contexto

ARCHIVO_CASOS = RAIZ_REPO / "data" / "evaluacion" / "bloque27_casos.json"
ARCHIVO_RESULTADOS_JSON = RAIZ_REPO / "docs" / "resultados_evaluacion_bloque27.json"
ARCHIVO_RESULTADOS_MD = RAIZ_REPO / "docs" / "resultados_evaluacion_bloque27.md"
INDICES = {"base": CONFIG_BLOQUE24, "markdown": CONFIG_BLOQUE26_MD}
KS_POR_DEFECTO = (3, 5)
CANDIDATOS = 20
MINIMO_CASOS, MAXIMO_CASOS = 8, 15
FRASE_ABSTENCION = "no contiene informacion suficiente"


class DatasetInvalidoError(ErrorRAG, ValueError):
    """Dataset de evaluación mal formado, no congelado o modificado tras el congelado."""


@dataclass(frozen=True)
class Configuracion:
    nombre: str
    indice: str
    nivel: str          # "chunk" o "seccion"
    metodo: str         # "vectorial" o "hibrido"
    expansion: bool


CONFIGURACIONES = (
    Configuracion("indice_original", "base", "chunk", "vectorial", False),
    Configuracion("markdown", "markdown", "chunk", "vectorial", False),
    Configuracion("markdown_expandido", "markdown", "seccion", "vectorial", True),
)
CONFIGURACIONES_HIBRIDAS = (
    Configuracion("markdown_hibrido", "markdown", "chunk", "hibrido", False),
    Configuracion("markdown_hibrido_expandido", "markdown", "seccion", "hibrido", True),
)


# --- Dataset ---------------------------------------------------------------------------

def huella_etiquetas(casos: list[dict]) -> str:
    """SHA-256 de preguntas, pasajes y etiquetas: detecta cambios posteriores al congelado."""
    contenido = [{k: c.get(k) for k in ("id", "pregunta", "sin_respuesta", "pasajes", "relevantes")} for c in casos]
    return hashlib.sha256(json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def validar_dataset(datos: dict, exigir_congelado: bool = True) -> None:
    casos = datos.get("casos")
    if not isinstance(casos, list) or not MINIMO_CASOS <= len(casos) <= MAXIMO_CASOS:
        raise DatasetInvalidoError(f"El dataset debe tener entre {MINIMO_CASOS} y {MAXIMO_CASOS} casos.")
    ids = [c.get("id") for c in casos]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
        raise DatasetInvalidoError("Los IDs de los casos deben ser cadenas únicas y no vacías.")
    if not any(c.get("sin_respuesta") for c in casos):
        raise DatasetInvalidoError("El dataset necesita al menos un caso sin respuesta.")
    for c in casos:
        for campo in ("pregunta", "tema", "justificacion"):
            if not isinstance(c.get(campo), str) or not c[campo].strip():
                raise DatasetInvalidoError(f"Caso {c['id']}: falta '{campo}'.")
        if not isinstance(c.get("sin_respuesta"), bool):
            raise DatasetInvalidoError(f"Caso {c['id']}: 'sin_respuesta' debe ser booleano.")
        pasajes = c.get("pasajes", [])
        if c["sin_respuesta"] != (not pasajes):
            raise DatasetInvalidoError(f"Caso {c['id']}: los casos sin respuesta no llevan pasajes y los demás sí.")
        for p in pasajes:
            if not p.get("fuente") or not p.get("texto"):
                raise DatasetInvalidoError(f"Caso {c['id']}: cada pasaje necesita 'fuente' y 'texto'.")
        if exigir_congelado:
            relevantes = c.get("relevantes")
            if not isinstance(relevantes, dict) or set(relevantes) != set(INDICES):
                raise DatasetInvalidoError(f"Caso {c['id']}: faltan etiquetas para los índices {sorted(INDICES)}.")
            for indice, etiquetas in relevantes.items():
                if c["sin_respuesta"] and (etiquetas.get("chunks") or etiquetas.get("secciones")):
                    raise DatasetInvalidoError(f"Caso {c['id']}: un caso sin respuesta no puede tener relevantes.")
                if not c["sin_respuesta"] and not etiquetas.get("chunks"):
                    raise DatasetInvalidoError(f"Caso {c['id']}: el índice {indice} no tiene chunks relevantes.")
    if exigir_congelado:
        if not datos.get("congelado"):
            raise DatasetInvalidoError("El dataset no está congelado: ejecuta primero --etiquetar.")
        if datos.get("huella_etiquetas") != huella_etiquetas(casos):
            raise DatasetInvalidoError("Las etiquetas cambiaron después del congelado (huella distinta).")


def cargar_dataset(ruta: Path = ARCHIVO_CASOS, exigir_congelado: bool = True) -> dict:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    validar_dataset(datos, exigir_congelado)
    return datos


def etiquetar(datos: dict, chunks_por_indice: dict[str, list[Document]], textos_fuente: dict[str, str],
              fecha: str) -> dict:
    """Deriva los IDs relevantes de los pasajes (sin ranking) y congela el dataset."""
    validar_dataset(datos, exigir_congelado=False)
    if datos.get("congelado"):
        raise DatasetInvalidoError(f"El dataset ya está congelado ({datos['congelado']}); no se reetiqueta.")
    for caso in datos["casos"]:
        for p in caso["pasajes"]:
            if p["fuente"] not in textos_fuente or not pasaje_existe_en_fuente(textos_fuente[p["fuente"]], p["texto"]):
                raise DatasetInvalidoError(f"Caso {caso['id']}: el pasaje no aparece literalmente en {p['fuente']}: {p['texto'][:60]!r}")
        caso["relevantes"] = {}
        for indice, chunks in chunks_por_indice.items():
            ids: list[str] = []
            for p in caso["pasajes"]:
                for i in chunks_relevantes(chunks, p["fuente"], [p["texto"]]):
                    if i not in ids:
                        ids.append(i)
            if not caso["sin_respuesta"] and not ids:
                raise DatasetInvalidoError(f"Caso {caso['id']}: ningún chunk del índice {indice} contiene los pasajes.")
            etiquetas = {"chunks": ids}
            secciones = secciones_de(chunks, ids)
            if secciones:
                etiquetas["secciones"] = secciones
            caso["relevantes"][indice] = etiquetas
    datos["congelado"] = fecha
    datos["huella_etiquetas"] = huella_etiquetas(datos["casos"])
    validar_dataset(datos, exigir_congelado=True)
    return datos


# --- Evaluación ------------------------------------------------------------------------

def unidades_de_contexto(almacen, ranking: list[Document], k: int,
                         max_seccion: int = MAX_CARACTERES_SECCION) -> list[Document]:
    """Las unidades que llegarían al generador (misma lógica que `generador.recuperar`)."""
    return [d for _, d in expandir_hasta_k(almacen, ranking, k, max_seccion)]


def ids_de_unidades(unidades: list[Document], nivel: str) -> list[str]:
    if nivel == "chunk":
        return [u.id for u in unidades]
    ids = []
    for u in unidades:
        s = id_seccion(u.metadata)
        if s is None:
            raise ValueError(f"La unidad {u.id} no tiene sección: el nivel 'seccion' requiere el índice markdown.")
        ids.append(s)
    return ids


def medir(unidades: list[Document], relevantes: list[str], nivel: str, k: int) -> dict:
    """Métricas de un caso en k, más el tamaño del contexto que se formaría con esas unidades."""
    seleccion = unidades[:k]
    resultado = metricas_en_k(ids_de_unidades(seleccion, nivel), relevantes, k)
    contexto, _ = formatear_contexto(seleccion)
    resultado["unidades"] = len(seleccion)
    resultado["caracteres_contexto"] = len(contexto)
    resultado["chunks_en_contexto"] = sum(len(u.metadata.get("chunk_ids_expandidos", [u.id])) for u in seleccion)
    return resultado


def evaluar_caso(caso: dict, rankings: dict[str, list[Document]], almacenes: dict, configuraciones,
                 ks=KS_POR_DEFECTO, max_seccion: int = MAX_CARACTERES_SECCION) -> dict:
    """`rankings[(indice, metodo)]` son listas de chunks ordenadas; no se llama a ninguna API aquí."""
    salida = {}
    for cfg in configuraciones:
        ranking = rankings[(cfg.indice, cfg.metodo)]
        unidades = unidades_de_contexto(almacenes[cfg.indice], ranking, max(ks), max_seccion) \
            if cfg.expansion else ranking[:max(ks)]
        etiquetas = caso["relevantes"][cfg.indice]
        relevantes = etiquetas["chunks"] if cfg.nivel == "chunk" else etiquetas.get("secciones", [])
        salida[cfg.nombre] = {str(k): medir(unidades, relevantes, cfg.nivel, k) for k in ks}
    return salida


def agregar(por_caso: dict[str, dict], casos: list[dict], configuraciones, ks=KS_POR_DEFECTO) -> dict:
    """Promedios sobre casos con respuesta; los casos sin respuesta quedan fuera del recall."""
    respondibles = [c["id"] for c in casos if not c["sin_respuesta"]]
    resumen = {}
    for cfg in configuraciones:
        resumen[cfg.nombre] = {}
        for k in ks:
            filas = [por_caso[i][cfg.nombre][str(k)] for i in respondibles]
            resumen[cfg.nombre][str(k)] = {
                m: promedio(f[m] for f in filas) for m in ("precision", "recall", "f1", "hit")
            } | {"caracteres_contexto": promedio(f["caracteres_contexto"] for f in filas),
                 "chunks_en_contexto": promedio(f["chunks_en_contexto"] for f in filas),
                 "casos_sin_respuesta_excluidos": len(casos) - len(respondibles)}
    return resumen


def peores_casos(por_caso: dict[str, dict], casos: list[dict], configuracion: str, k: int, n: int = 3) -> list[dict]:
    filas = []
    for c in casos:
        if c["sin_respuesta"]:
            continue
        m = por_caso[c["id"]][configuracion][str(k)]
        filas.append({"id": c["id"], "recall": m["recall"], "f1": m["f1"], "precision": m["precision"]})
    return sorted(filas, key=lambda f: (f["recall"], f["f1"], f["id"]))[:n]


def detectar_abstencion(respuesta: str) -> bool:
    return FRASE_ABSTENCION in normalizar(respuesta) or "no hay informacion suficiente" in normalizar(respuesta)


def comparar_ejecuciones(a: dict, b: dict) -> dict:
    """Diferencias de rankings y de promedios entre dos ejecuciones (estabilidad)."""
    cambios_ranking = []
    for caso_id, por_cfg in a["por_caso"].items():
        for cfg, por_k in por_cfg.items():
            otro = b["por_caso"].get(caso_id, {}).get(cfg)
            if otro is None:
                continue
            for k, m in por_k.items():
                if m["recuperados"] != otro[k]["recuperados"]:
                    cambios_ranking.append({"caso": caso_id, "configuracion": cfg, "k": k})
    cambios_metricas = []
    for cfg, por_k in a["agregados"].items():
        for k, metricas in por_k.items():
            for nombre in ("precision", "recall", "f1", "hit"):
                va, vb = metricas[nombre]["media"], b["agregados"].get(cfg, {}).get(k, {}).get(nombre, {}).get("media")
                if va != vb:
                    cambios_metricas.append({"configuracion": cfg, "k": k, "metrica": nombre, "a": va, "b": vb})
    return {"rankings_distintos": cambios_ranking, "promedios_distintos": cambios_metricas,
            "identicas": not cambios_ranking and not cambios_metricas}


def construir_rankings(almacenes: dict, pregunta: str, metodos: set[str], indices_bm25: dict,
                       candidatos: int = CANDIDATOS) -> tuple[dict, dict]:
    """Una búsqueda vectorial por índice (una embed_query). BM25/RRF reutiliza ese ranking."""
    rankings, distancias = {}, {}
    for nombre, almacen in almacenes.items():
        pares = buscar_con_score(almacen, pregunta, candidatos)
        rankings[(nombre, "vectorial")] = [d for d, _ in pares]
        distancias[nombre] = [round(float(s), 4) for _, s in pares[:5]]
        if "hibrido" in metodos:
            lexicos = [(r.documento, r.puntaje) for r in indices_bm25[nombre].buscar(pregunta, candidatos)]
            rankings[(nombre, "hibrido")] = [r.documento for r in fusionar_rrf(pares, lexicos, candidatos)]
    return rankings, distancias


def describir_indice(almacen, config: ConfiguracionIndice) -> dict:
    """Se lee de la colección persistida; no se asume la configuración."""
    coleccion = almacen._collection
    datos = coleccion.get(include=["metadatas"])
    meta = coleccion.metadata or {}
    return {
        "coleccion": coleccion.name,
        "directorio": Path(config.directorio).relative_to(RAIZ_REPO).as_posix(),
        "modelo_embeddings": meta.get("modelo_embeddings"),
        "estrategia": meta.get("estrategia"),
        "chunk_size": meta.get("chunk_size"),
        "chunk_overlap": meta.get("chunk_overlap"),
        "distancia": meta.get("hnsw:space"),
        "chunks": coleccion.count(),
        "documentos": len({m.get("fuente") for m in datos["metadatas"]}),
        "secciones": len({id_seccion(m) for m in datos["metadatas"] if id_seccion(m)}),
    }


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def guardar_ejecucion(ejecucion: dict, ruta: Path = ARCHIVO_RESULTADOS_JSON) -> dict:
    """Agrega la ejecución al historial (nunca borra las anteriores)."""
    ruta = Path(ruta)
    historial = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"ejecuciones": []}
    if any(e["id_ejecucion"] == ejecucion["id_ejecucion"] for e in historial["ejecuciones"]):
        raise DatasetInvalidoError(f"Ya existe una ejecución con id {ejecucion['id_ejecucion']}.")
    historial["ejecuciones"].append(ejecucion)
    ruta.write_text(json.dumps(historial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return historial
