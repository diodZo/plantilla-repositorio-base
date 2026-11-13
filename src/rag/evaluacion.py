"""Evaluación de recuperación: vectorial vs. léxica vs. híbrida, con Hit@k.

Dos criterios de acierto:
- por fuente: algún chunk recuperado proviene de una fuente esperada;
- por evidencia (estricto): ese chunk además contiene una de las subcadenas de evidencia.
El criterio estricto evita contar como acierto un chunk del documento correcto
que no contiene la respuesta (lo que ocurría en el escenario B).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document

from src.rag.configuracion import RAIZ_REPO
from src.rag.expansion import expandir_resultados
from src.rag.hibrido import fusionar_rrf
from src.rag.lexico import IndiceBM25, normalizar
from src.rag.recuperador import buscar_con_score

ARCHIVO_CONSULTAS = RAIZ_REPO / "data" / "evaluacion" / "consultas_recuperacion.json"  # desarrollo (7 + 2)
ARCHIVO_VALIDACION = RAIZ_REPO / "data" / "evaluacion" / "consultas_validacion.json"  # validación (6 + 2)
CONJUNTOS = {"desarrollo": ARCHIVO_CONSULTAS, "validacion": ARCHIVO_VALIDACION}
METODOS = ("vectorial", "lexico", "hibrido")


@dataclass(frozen=True)
class ConsultaEvaluacion:
    id: str
    tema: str
    pregunta: str
    fuentes: tuple[str, ...]
    evidencia: tuple[str, ...]


@dataclass
class ResultadoConsulta:
    consulta: ConsultaEvaluacion
    rankings: dict[str, list[Document]] = field(default_factory=dict)
    detalle: dict[str, list[dict]] = field(default_factory=dict)


def cargar_consultas(ruta: Path = ARCHIVO_CONSULTAS) -> list[ConsultaEvaluacion]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return [ConsultaEvaluacion(c["id"], c["tema"], c["pregunta"], tuple(c["fuentes"]), tuple(c["evidencia"]))
            for c in datos["consultas"]]


def es_acierto(documento: Document, consulta: ConsultaEvaluacion, estricto: bool) -> bool:
    if documento.metadata.get("fuente") not in consulta.fuentes:
        return False
    if not estricto:
        return True
    texto = normalizar(documento.page_content)
    return any(normalizar(e) in texto for e in consulta.evidencia)


def primer_acierto(documentos: list[Document], consulta: ConsultaEvaluacion, estricto: bool = True) -> int | None:
    """Posición (desde 1) del primer acierto, o None."""
    for posicion, documento in enumerate(documentos, start=1):
        if es_acierto(documento, consulta, estricto):
            return posicion
    return None


def hit_at_k(documentos: list[Document], consulta: ConsultaEvaluacion, k: int, estricto: bool = True) -> bool | None:
    """None si la consulta no tiene fuente esperada (fuera del corpus)."""
    if not consulta.fuentes:
        return None
    posicion = primer_acierto(documentos, consulta, estricto)
    return posicion is not None and posicion <= k


def evaluar_consulta(
    almacen, indice: IndiceBM25, consulta: ConsultaEvaluacion, profundidad: int = 20,
    candidatos: int = 20, k_rrf: int = 60, expandir: bool = False,
) -> ResultadoConsulta:
    """Una sola llamada a embed_query: el ranking vectorial se reutiliza para la fusión."""
    n = max(profundidad, candidatos)
    vectoriales = buscar_con_score(almacen, consulta.pregunta, n)
    lexicos = [(r.documento, r.puntaje) for r in indice.buscar(consulta.pregunta, n)]
    hibridos = fusionar_rrf(vectoriales[:candidatos], lexicos[:candidatos], profundidad, k_rrf)
    resultado = ResultadoConsulta(consulta)
    resultado.rankings = {
        "vectorial": [d for d, _ in vectoriales[:profundidad]],
        "lexico": [d for d, _ in lexicos[:profundidad]],
        "hibrido": [r.documento for r in hibridos],
    }
    if expandir:
        resultado.rankings = {m: expandir_resultados(almacen, docs) for m, docs in resultado.rankings.items()}
    resultado.detalle = {
        "vectorial": [{"id": d.id, "fuente": d.metadata.get("fuente"), "distancia": round(float(s), 4)}
                      for d, s in vectoriales[:5]],
        "lexico": [{"id": d.id, "fuente": d.metadata.get("fuente"), "bm25": round(float(s), 3)}
                   for d, s in lexicos[:5]],
        "hibrido": [{"id": r.documento.id, "fuente": r.documento.metadata.get("fuente"),
                     "rrf": round(r.puntaje_rrf, 5), "rango_vectorial": r.rango_vectorial,
                     "rango_lexico": r.rango_lexico} for r in hibridos[:5]],
    }
    return resultado


def resumir(resultados: list[ResultadoConsulta], ks: tuple[int, ...] = (3, 5)) -> dict:
    """Hit@k por método (estricto y por fuente) sobre las consultas con fuente esperada."""
    con_fuente = [r for r in resultados if r.consulta.fuentes]
    resumen: dict = {"consultas_con_fuente": len(con_fuente), "metodos": {}}
    for metodo in METODOS:
        datos = {}
        for k in ks:
            for estricto, etiqueta in ((True, "evidencia"), (False, "fuente")):
                aciertos = sum(bool(hit_at_k(r.rankings[metodo], r.consulta, k, estricto)) for r in con_fuente)
                datos[f"hit@{k}_{etiqueta}"] = round(aciertos / len(con_fuente), 3) if con_fuente else None
        resumen["metodos"][metodo] = datos
    return resumen
