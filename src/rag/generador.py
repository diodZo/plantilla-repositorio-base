"""Generación de la respuesta, separada de la recuperación y del prompt.

Flujo: recuperar (recuperador.py) -> formatear contexto -> construir prompt (prompts.py)
-> invocar el modelo (aquí).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_core.documents import Document

from src.rag.configuracion import K_POR_DEFECTO, obtener_clave_api, obtener_modelo_chat
from src.rag.errores import DependenciaFaltanteError
from src.rag.expansion import MAX_CARACTERES_SECCION, clave_expandido, expandir_documento
from src.rag.hibrido import CANDIDATOS_POR_DEFECTO, K_RRF, buscar_hibrido
from src.rag.prompts import construir_prompt
from src.rag.recuperador import buscar_con_score, formatear_contexto
from src.rag.reintentos import llamar_con_reintentos

MODOS = ("vectorial", "hibrido")

RESPUESTA_SIN_CONTEXTO = (
    "No se recuperaron fragmentos de la documentación para esta pregunta; "
    "no hay información suficiente para responder."
)


@dataclass
class RespuestaRAG:
    pregunta: str
    respuesta: str
    citas: dict[int, str]
    distancias: list[float] = field(default_factory=list)
    contexto: str = ""
    modelo_invocado: bool = False
    metodo: str = "vectorial"
    puntajes: list[float] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)


@dataclass
class ResultadoRecuperado:
    documento: Document
    puntaje: float
    tipo_puntaje: str  # "distancia_coseno" (menor = mejor) o "rrf" (mayor = mejor)


def recuperar(
    almacen, pregunta: str, k: int = K_POR_DEFECTO, modo: str = "vectorial", expandir: bool = False,
    candidatos: int = CANDIDATOS_POR_DEFECTO, k_rrf: int = K_RRF,
    max_seccion: int = MAX_CARACTERES_SECCION,
) -> list[ResultadoRecuperado]:
    """Etapa de recuperación configurable. Por defecto equivale al recuperador original (vectorial, sin expansión).

    Con `expandir=True` se piden `max(k, candidatos)` candidatos, se expande cada uno a su
    sección y se deduplican las secciones repetidas hasta reunir k unidades.
    """
    if modo not in MODOS:
        raise ValueError(f"Modo desconocido: {modo!r}. Usa {MODOS}.")
    profundidad = max(k, candidatos) if expandir else k
    if modo == "vectorial":
        items = [ResultadoRecuperado(d, float(s), "distancia_coseno")
                 for d, s in buscar_con_score(almacen, pregunta, profundidad)]
    else:
        items = [ResultadoRecuperado(r.documento, r.puntaje_rrf, "rrf")
                 for r in buscar_hibrido(almacen, pregunta, profundidad, candidatos, candidatos, k_rrf)]
    if not expandir:
        return items[:k]
    vistos: set = set()
    expandidos: list[ResultadoRecuperado] = []
    for item in items:
        documento = expandir_documento(almacen, item.documento, max_seccion)
        clave = clave_expandido(item.documento, documento)
        if clave in vistos:
            continue
        vistos.add(clave)
        expandidos.append(ResultadoRecuperado(documento, item.puntaje, item.tipo_puntaje))
        if len(expandidos) == k:
            break
    return expandidos


def aplicar_limite_contexto(
    resultados: list[ResultadoRecuperado], max_caracteres: int | None,
) -> tuple[list[ResultadoRecuperado], list[ResultadoRecuperado]]:
    """Incluye unidades completas en orden de ranking mientras quepan en `max_caracteres`.

    Nunca recorta una unidad (no se corta el fragmento que contiene la evidencia). La
    primera unidad siempre se incluye completa aunque exceda el límite, para no dejar al
    modelo sin el resultado mejor clasificado. Se detiene en la primera que no cabe.
    """
    if max_caracteres is None:
        return list(resultados), []
    if max_caracteres < 1:
        raise ValueError("max_caracteres debe ser >= 1.")
    incluidos: list[ResultadoRecuperado] = []
    total = 0
    for posicion, resultado in enumerate(resultados):
        bloque = len(f"[{len(incluidos) + 1}] {resultado.documento.page_content.strip()}")
        costo = bloque + (2 if incluidos else 0)  # dos saltos de línea entre bloques
        if incluidos and total + costo > max_caracteres:
            return incluidos, list(resultados[posicion:])
        incluidos.append(resultado)
        total += costo
    return incluidos, []


def calcular_metricas(incluidos: list[ResultadoRecuperado], omitidos: list[ResultadoRecuperado],
                      contexto: str, citas: dict[int, str], respuesta: str = "") -> dict:
    """Métricas de tamaño de contexto y de citas usadas en la respuesta."""
    usadas = sorted({int(n) for n in re.findall(r"\[(\d+)\]", respuesta)})
    return {
        "unidades_contexto": len(incluidos),
        "unidades_omitidas_por_limite": len(omitidos),
        "chunks_recuperados": sum(len(r.documento.metadata.get("chunk_ids_expandidos", [r.documento.id]))
                                  for r in incluidos),
        "secciones_expandidas": sum(r.documento.metadata.get("expansion") == "seccion" for r in incluidos),
        "ventanas_expandidas": sum(r.documento.metadata.get("expansion") == "ventana" for r in incluidos),
        "caracteres_contexto": len(contexto),
        "fuentes_contexto": sorted(set(citas.values())),
        "citas_usadas": usadas,
        "fuentes_citadas": sorted({citas[n] for n in usadas if n in citas}),
        "citas_invalidas": [n for n in usadas if n not in citas],
    }


def preparar_contexto(
    almacen, pregunta: str, k: int = K_POR_DEFECTO, modo: str = "vectorial", expandir: bool = False,
    candidatos: int = CANDIDATOS_POR_DEFECTO, max_contexto: int | None = None,
    max_seccion: int = MAX_CARACTERES_SECCION,
):
    """Recuperación + límite + formato. Devuelve (incluidos, omitidos, contexto, citas)."""
    resultados = recuperar(almacen, pregunta, k, modo, expandir, candidatos, max_seccion=max_seccion)
    incluidos, omitidos = aplicar_limite_contexto(resultados, max_contexto)
    contexto, citas = formatear_contexto([r.documento for r in incluidos])
    return incluidos, omitidos, contexto, citas


def crear_modelo_chat(modelo: str | None = None):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as error:
        raise DependenciaFaltanteError(
            "Falta langchain-google-genai. Ejecuta: python -m pip install -r requirements.txt"
        ) from error
    # max_retries=0: la política de reintentos es la nuestra (solo transitorios).
    return ChatGoogleGenerativeAI(model=modelo or obtener_modelo_chat(),
                                  google_api_key=obtener_clave_api(), max_retries=0)


def texto_de_respuesta(mensaje) -> str:
    """Gemini puede devolver `content` como str o como lista de bloques."""
    contenido = getattr(mensaje, "content", mensaje)
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in contenido)
    return str(contenido)


def generar(modelo, prompt) -> str:
    return texto_de_respuesta(llamar_con_reintentos(lambda: modelo.invoke(prompt)))


def responder(almacen, modelo, pregunta: str, k: int = K_POR_DEFECTO, modo: str = "vectorial",
              expandir: bool = False, candidatos: int = CANDIDATOS_POR_DEFECTO,
              max_contexto: int | None = None) -> RespuestaRAG:
    """API de biblioteca. Sus valores por defecto conservan el comportamiento original
    (vectorial, sin expansión, sin límite); la CLI usa sus propios valores predeterminados."""
    incluidos, omitidos, contexto, citas = preparar_contexto(
        almacen, pregunta, k, modo, expandir, candidatos, max_contexto)
    if not incluidos:
        return RespuestaRAG(pregunta, RESPUESTA_SIN_CONTEXTO, {}, [], "", False, modo, [],
                            calcular_metricas([], omitidos, "", {}))
    texto = generar(modelo, construir_prompt(pregunta, contexto))
    distancias = [r.puntaje for r in incluidos if r.tipo_puntaje == "distancia_coseno"]
    return RespuestaRAG(pregunta, texto, citas, distancias, contexto, True, modo,
                        [r.puntaje for r in incluidos], calcular_metricas(incluidos, omitidos, contexto, citas, texto))
