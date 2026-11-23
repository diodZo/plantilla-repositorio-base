"""Consulta RAG auditada de principio a fin (Bloque 31).

Secuencia (cada evento se emite solo si la etapa ocurre de verdad):
  consulta_recibida → recuperacion_iniciada → recuperacion_finalizada
  → [documento_descartado_por_inyeccion]* → contexto_filtrado
  → (abstencion_sin_contexto | generacion_iniciada → generacion_finalizada [→ citas_invalidas])
  → [consumo_llm] → consulta_finalizada
Ante un error: consulta_fallida (con la etapa y el tipo) y la excepción se vuelve a lanzar.

Reutiliza el Bloque 28 (una sola `embed_query` + `buscar_por_vector_con_score`, `expandir_hasta_k`,
`Medidor`, `extraer_uso`, `desglose_costo`) y el Bloque 26 (`formatear_contexto`, `calcular_metricas`).
El filtro de inyección se aplica a las unidades FINALES (después de la expansión) y el contexto y
las citas se reconstruyen solo con las permitidas: la numeración [1..n] sale de `formatear_contexto`.

Los logs no contienen la pregunta ni el contenido de los documentos: solo longitudes, huellas
SHA-256, fuentes, patrones, tiempos y tokens.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from src.gobernanza.registro_prompts import identificar_prompt_enviado
from src.rag.costos import Tarifa, buscar_tarifa, desglose_costo, extraer_uso
from src.rag.expansion import MAX_CARACTERES_SECCION, expandir_hasta_k
from src.rag.generador import RESPUESTA_SIN_CONTEXTO, ResultadoRecuperado, calcular_metricas, texto_de_respuesta
from src.rag.hibrido import CANDIDATOS_POR_DEFECTO
from src.rag.logging_json import huella, registrar_evento
from src.rag.medicion import Medidor
from src.rag.recuperador import _validar_consulta, buscar_por_vector_con_score, formatear_contexto, verificar_no_vacio
from src.rag.reintentos import llamar_con_reintentos
from src.rag.seguridad_prompt import ResultadoFiltro, UnidadDescartada, construir_prompt_seguro, detectar_inyeccion, \
    filtrar_unidades
from src.rag.trazabilidad import contexto_traza

RESPUESTA_TODO_DESCARTADO = (
    "Los fragmentos recuperados se descartaron por contener patrones de inyección de prompt; "
    "no hay información confiable suficiente para responder."
)


class ContextoContaminadoError(RuntimeError):
    """Una unidad en cuarentena apareció en el prompt final. No debe ocurrir; se detiene la consulta."""


class RecuperadorSmallToBig(BaseRetriever):
    """Retriever de LangChain: 1 `embed_query` → búsqueda por vector → expansión small-to-big.

    Devuelve las unidades FINALES del contexto (las que llegarían al modelo), con
    `posicion_origen` = posición del chunk recuperado en el ranking. Al ser un `BaseRetriever`,
    dispara `on_retriever_start/end/error` en los callbacks.
    """

    almacen: Any
    embeddings: Any
    k: int = 3
    expandir: bool = True
    candidatos: int = CANDIDATOS_POR_DEFECTO
    max_seccion: int = MAX_CARACTERES_SECCION

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        _validar_consulta(query, self.k)
        verificar_no_vacio(self.almacen)
        vector = self.embeddings.embed_query(query)
        profundidad = max(self.k, self.candidatos) if self.expandir else self.k
        documentos = [d for d, _ in buscar_por_vector_con_score(self.almacen, vector, profundidad)]
        unidades = (expandir_hasta_k(self.almacen, documentos, self.k, self.max_seccion) if self.expandir
                    else list(enumerate(documentos[: self.k])))
        return [Document(id=u.id, page_content=u.page_content, metadata={**u.metadata, "posicion_origen": p})
                for p, u in unidades]


@dataclass
class RespuestaAuditada:
    trace_id: str
    estado: str  # "ok" o "abstencion"
    respuesta: str
    citas: dict[int, str]
    descartadas: list[dict] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)
    consumo: dict | None = None
    tiempos: dict = field(default_factory=dict)
    prompt_mensajes: list = field(default_factory=list)  # Solo en memoria: nunca se escribe en el log.
    prompt: dict | None = None  # Identificación de la versión del prompt enviado (Bloque 32).
    textos_citas: dict = field(default_factory=dict)  # {n: texto de la unidad [n]}; solo en memoria (Gate 2).


def descripcion_unidad(unidad: UnidadDescartada) -> dict:
    """Metadatos de auditoría de una unidad descartada (sin su contenido)."""
    md = unidad.documento.metadata
    return {
        "fuente": md.get("fuente"),
        "documento_id": md.get("documento_id"),
        "seccion": md.get("seccion") or None,
        "chunk_recuperado": md.get("chunk_recuperado", unidad.documento.id),
        "posicion_contexto": unidad.posicion,
        "patrones": unidad.patrones,
        "caracteres": len(unidad.documento.page_content),
        "huella_contenido": huella(unidad.documento.page_content),
    }


def verificar_sin_cuarentena(mensajes: list, cuarentena: list[UnidadDescartada]) -> None:
    """Comprueba que ningún texto en cuarentena haya llegado al prompt por otra ruta."""
    texto_prompt = "\n".join(str(m.content) for m in mensajes)
    for unidad in cuarentena:
        if unidad.documento.page_content.strip() and unidad.documento.page_content.strip() in texto_prompt:
            raise ContextoContaminadoError(
                f"Una unidad en cuarentena ({unidad.documento.metadata.get('fuente')}) apareció en el prompt.")


def _fuentes(documentos: list[Document]) -> list[str]:
    return sorted({d.metadata.get("fuente") for d in documentos if d.metadata.get("fuente")})


def _consumo(mensaje, modelo_generacion: str, tipo_medicion: str, pregunta: str, tarifas: dict[str, Tarifa] | None,
             modelo_embeddings: str | None, medidor: Medidor) -> dict:
    uso = extraer_uso(mensaje)
    consumo = {
        "modelo": modelo_generacion,
        "tipo_medicion": tipo_medicion,
        "estado_uso": uso["estado"],
        "input_tokens": uso["entrada"],
        "output_tokens": uso["salida"],
        "total_tokens": uso["total"],
        "razonamiento_tokens": uso["razonamiento"],
        "tiempo_generacion_ms": round(medidor.tiempos_ms["generacion"], 3),
        "tiempo_total_ms": None if medidor.total_ms is None else round(medidor.total_ms, 3),
        "costo_estimado_usd": None,
        "costo_estado": "desconocido: sin tarifas",
    }
    if tarifas is not None:
        tarifa_gen = buscar_tarifa(tarifas, modelo_generacion)
        tarifa_emb = buscar_tarifa(tarifas, modelo_embeddings) if modelo_embeddings else None
        desglose = desglose_costo(uso, tarifa_gen, pregunta, tarifa_emb)
        consumo["costo_estimado_usd"] = desglose["generacion"]["total_usd"]
        consumo["costo_estado"] = desglose["generacion"]["estado"]
    return consumo


def consultar_auditado(
    almacen, embeddings, modelo, pregunta: str, *, logger: logging.Logger, modelo_generacion: str,
    tipo_medicion: str = "real", tarifas: dict[str, Tarifa] | None = None, modelo_embeddings: str | None = None,
    k: int = 3, expandir: bool = True, candidatos: int = CANDIDATOS_POR_DEFECTO,
    max_seccion: int = MAX_CARACTERES_SECCION, callbacks: list | None = None, trace_id: str | None = None,
    minimo_unidades: int = 1,
) -> RespuestaAuditada:
    """Consulta RAG con filtro de inyección, citas reconstruidas y traza completa en `logger`."""
    if tipo_medicion not in ("real", "simulada"):
        raise ValueError("tipo_medicion debe ser 'real' o 'simulada'.")
    if minimo_unidades < 1:
        raise ValueError("minimo_unidades debe ser >= 1.")
    configuracion = {"callbacks": callbacks} if callbacks else None
    recuperador = RecuperadorSmallToBig(almacen=almacen, embeddings=embeddings, k=k, expandir=expandir,
                                        candidatos=candidatos, max_seccion=max_seccion)

    with contexto_traza(trace_id) as tid:
        medidor = Medidor()
        etapa = "consulta_recibida"
        registrar_evento(logger, "consulta_recibida", pregunta_len=len(pregunta) if isinstance(pregunta, str) else None,
                         pregunta_huella=huella(pregunta) if isinstance(pregunta, str) else None,
                         k=k, expandir=expandir, modelo=modelo_generacion, tipo_medicion=tipo_medicion)
        if isinstance(pregunta, str) and (patrones := detectar_inyeccion(pregunta)):
            # Solo se registra: la pregunta es del usuario y el modelo de amenaza aquí es la inyección indirecta.
            registrar_evento(logger, "pregunta_con_patron_sospechoso", logging.WARNING, patrones=patrones)
        mensaje = None
        resultado: RespuestaAuditada | None = None
        try:
            with medidor.total():
                etapa = "recuperacion"
                registrar_evento(logger, "recuperacion_iniciada", k=k, expandir=expandir)
                with medidor.etapa("recuperacion"):
                    unidades = recuperador.invoke(pregunta, config=configuracion)
                registrar_evento(logger, "recuperacion_finalizada", unidades_recuperadas=len(unidades),
                                 fuentes=_fuentes(unidades), posiciones_origen=[u.metadata.get("posicion_origen")
                                                                               for u in unidades],
                                 chunks_en_unidades=sum(len(u.metadata.get("chunk_ids_expandidos", [u.id]))
                                                        for u in unidades),
                                 duracion_ms=round(medidor.tiempos_ms["recuperacion"], 3))

                etapa = "filtrado"
                with medidor.etapa("filtrado"):
                    filtro: ResultadoFiltro = filtrar_unidades(unidades)
                descartadas = [descripcion_unidad(u) for u in filtro.cuarentena]
                for descripcion in descartadas:
                    registrar_evento(logger, "documento_descartado_por_inyeccion", logging.WARNING, **descripcion)
                registrar_evento(logger, "contexto_filtrado", unidades_recuperadas=filtro.total,
                                 unidades_descartadas=len(filtro.cuarentena), unidades_permitidas=len(filtro.permitidos),
                                 fuentes_permitidas=_fuentes(filtro.permitidos),
                                 fuentes_descartadas=sorted({d["fuente"] for d in descartadas if d["fuente"]}))

                if len(filtro.permitidos) < minimo_unidades:
                    motivo = "sin_unidades_recuperadas" if not unidades else (
                        "todas_descartadas_por_inyeccion" if not filtro.permitidos else "contexto_insuficiente")
                    registrar_evento(logger, "abstencion_sin_contexto", logging.WARNING, motivo=motivo,
                                     unidades_permitidas=len(filtro.permitidos))
                    texto = RESPUESTA_SIN_CONTEXTO if not unidades else RESPUESTA_TODO_DESCARTADO
                    resultado = RespuestaAuditada(tid, "abstencion", texto, {}, descartadas,
                                                  calcular_metricas([], [], "", {}))
                else:
                    etapa = "construccion_prompt"
                    with medidor.etapa("construccion_prompt"):
                        contexto, citas = formatear_contexto(filtro.permitidos)
                        mensajes = construir_prompt_seguro(pregunta, contexto).to_messages()
                        verificar_sin_cuarentena(mensajes, filtro.cuarentena)
                    # Bloque 32: qué versión registrada corresponde al texto REALMENTE enviado (no lo cambia).
                    prompt_info = identificar_prompt_enviado(mensajes)
                    registrar_evento(logger, "generacion_iniciada", **prompt_info, modelo=modelo_generacion,
                                     unidades_contexto=len(filtro.permitidos), roles=[m.type for m in mensajes],
                                     caracteres_contexto=len(contexto),
                                     caracteres_prompt=sum(len(str(m.content)) for m in mensajes))

                    etapa = "generacion"
                    intentos: list[int] = []

                    def invocar():
                        intentos.append(1)
                        if configuracion:
                            return modelo.invoke(mensajes, config=configuracion)
                        return modelo.invoke(mensajes)

                    with medidor.etapa("generacion"):
                        mensaje = llamar_con_reintentos(invocar)
                    texto = texto_de_respuesta(mensaje)
                    incluidos = [ResultadoRecuperado(d, float("nan"), "no_aplica") for d in filtro.permitidos]
                    metricas = calcular_metricas(incluidos, [], contexto, citas, texto)  # validación del Bloque 26
                    registrar_evento(logger, "generacion_finalizada", respuesta_caracteres=len(texto),
                                     intentos=len(intentos), citas_usadas=metricas["citas_usadas"],
                                     citas_invalidas=metricas["citas_invalidas"],
                                     fuentes_citadas=metricas["fuentes_citadas"],
                                     duracion_ms=round(medidor.tiempos_ms["generacion"], 3))
                    if metricas["citas_invalidas"]:
                        registrar_evento(logger, "citas_invalidas", logging.WARNING,
                                         citas_invalidas=metricas["citas_invalidas"], citas_disponibles=sorted(citas))
                    resultado = RespuestaAuditada(tid, "ok", texto, citas, descartadas, metricas,
                                                  prompt_mensajes=mensajes, prompt=prompt_info,
                                                  textos_citas={n: d.page_content for n, d in
                                                                enumerate(filtro.permitidos, start=1)})
        except Exception as error:
            registrar_evento(logger, "consulta_fallida", logging.ERROR, etapa=etapa, error_tipo=type(error).__name__,
                             etapas_fallidas=list(medidor.etapas_fallidas),
                             tiempo_total_ms=None if medidor.total_ms is None else round(medidor.total_ms, 3))
            raise

        resultado.tiempos = medidor.como_dict(("recuperacion", "filtrado", "construccion_prompt", "generacion"))
        if mensaje is not None:
            resultado.consumo = _consumo(mensaje, modelo_generacion, tipo_medicion, pregunta, tarifas,
                                         modelo_embeddings, medidor)
            registrar_evento(logger, "consumo_llm", **resultado.consumo)
        registrar_evento(logger, "consulta_finalizada", estado=resultado.estado,
                         unidades_finales=len(resultado.citas), fuentes_utilizadas=sorted(set(resultado.citas.values())),
                         unidades_descartadas=len(resultado.descartadas), **resultado.tiempos)
        return resultado
