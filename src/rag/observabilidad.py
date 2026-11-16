"""Consulta RAG instrumentada, registro JSONL y estadísticas (Bloque 28).

Flujo medido (configuración predeterminada: índice markdown, vectorial, expansión, k=3):
  validacion_indice → embed_query → busqueda_vectorial → expansion_contexto
  → construccion_prompt → generacion
Una sola `embed_query` por pregunta: la búsqueda usa el vector ya calculado
(`buscar_por_vector_con_score`), no vuelve a embeber la pregunta.
"""
from __future__ import annotations

import json
import re
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.rag.configuracion import RAIZ_REPO
from src.rag.costos import Tarifa, buscar_tarifa, desglose_costo, extraer_uso
from src.rag.etiquetado import id_seccion
from src.rag.expansion import MAX_CARACTERES_SECCION, expandir_hasta_k
from src.rag.generador import texto_de_respuesta
from src.rag.hibrido import CANDIDATOS_POR_DEFECTO
from src.rag.medicion import Medidor
from src.rag.prompts import construir_prompt
from src.rag.recuperador import _validar_consulta, buscar_por_vector_con_score, formatear_contexto, verificar_no_vacio
from src.rag.reintentos import llamar_con_reintentos

ARCHIVO_REGISTROS = RAIZ_REPO / "registros_latencia_costo.jsonl"
ETAPAS = ("validacion_indice", "embed_query", "busqueda_vectorial", "expansion_contexto",
          "construccion_prompt", "generacion")
VERSION_REGISTRO = 1


@dataclass(frozen=True)
class ContextoConsulta:
    """Lo que describe la ejecución, sin secretos."""
    indice: str
    coleccion: str
    modelo_embeddings: str
    modelo_generacion: str
    tipo_medicion: str = "real"   # "real" o "simulada"
    id_ejecucion: str = ""


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def nuevo_id_ejecucion() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def consultar_instrumentado(
    almacen, embeddings, modelo, pregunta: str, contexto_ejecucion: ContextoConsulta,
    tarifas: dict[str, Tarifa], k: int = 3, expandir: bool = True,
    candidatos: int = CANDIDATOS_POR_DEFECTO, max_seccion: int = MAX_CARACTERES_SECCION,
    generar: bool = True, medidor: Medidor | None = None,
) -> dict:
    """Ejecuta la consulta completa y devuelve el registro. Si una etapa falla, el registro
    queda con estado 'error' y los tiempos disponibles en `registro['_excepcion']`; quien
    llama decide guardarlo y la excepción NO se oculta (se vuelve a lanzar con `relanzar`)."""
    medidor = medidor or Medidor()
    registro = {
        "version": VERSION_REGISTRO,
        "id_ejecucion": contexto_ejecucion.id_ejecucion,
        "id_consulta": uuid.uuid4().hex[:12],
        "timestamp": ahora_utc(),
        "tipo_medicion": contexto_ejecucion.tipo_medicion,
        "pregunta": pregunta,
        "modelo_generacion": contexto_ejecucion.modelo_generacion if generar else None,
        "modelo_embeddings": contexto_ejecucion.modelo_embeddings,
        "indice": contexto_ejecucion.indice,
        "coleccion": contexto_ejecucion.coleccion,
        "modo": "vectorial",
        "expandir": expandir,
        "k": k,
        "candidatos": candidatos if expandir else k,
        "estado": "en_curso",
        "error": None,
    }
    resultado: dict = {}
    try:
        with medidor.total():
            with medidor.etapa("validacion_indice"):
                _validar_consulta(pregunta, k)
                verificar_no_vacio(almacen)
            with medidor.etapa("embed_query"):
                vector = embeddings.embed_query(pregunta)
            profundidad = max(k, candidatos) if expandir else k
            with medidor.etapa("busqueda_vectorial"):
                pares = buscar_por_vector_con_score(almacen, vector, profundidad)
            with medidor.etapa("expansion_contexto"):
                documentos = [d for d, _ in pares]
                if expandir:
                    unidades = expandir_hasta_k(almacen, documentos, k, max_seccion)
                else:
                    unidades = list(enumerate(documentos[:k]))
            with medidor.etapa("construccion_prompt"):
                contexto, citas = formatear_contexto([u for _, u in unidades])
                prompt = construir_prompt(pregunta, contexto)
                texto_prompt = "\n".join(m.content for m in prompt.to_messages())
            resultado.update(pares=pares, unidades=unidades, contexto=contexto, citas=citas, prompt=texto_prompt)
            if generar:
                intentos = []

                def invocar():
                    intentos.append(1)
                    return modelo.invoke(prompt)
                with medidor.etapa("generacion"):
                    mensaje = llamar_con_reintentos(invocar)
                resultado.update(mensaje=mensaje, intentos_generacion=len(intentos))
        registro["estado"] = "ok"
    except Exception as error:  # se registra y se vuelve a lanzar desde `relanzar`
        registro["estado"] = "error"
        registro["error"] = {"tipo": type(error).__name__, "mensaje": str(error)[:300],
                             "etapas_fallidas": list(medidor.etapas_fallidas)}
        registro["_excepcion"] = error
    _completar_registro(registro, resultado, medidor, tarifas, generar, pregunta)
    return registro


def _completar_registro(registro: dict, r: dict, medidor: Medidor, tarifas, generar: bool, pregunta: str) -> None:
    tiempos = medidor.como_dict(ETAPAS if generar else ETAPAS[:-1])
    registro.update(tiempos)
    unidades = [u for _, u in r.get("unidades", [])]
    registro["recuperacion"] = {
        "chunks_candidatos": len(r.get("pares", [])),
        "unidades_contexto": len(unidades),
        "secciones_unicas": len({id_seccion(u.metadata) for u in unidades if id_seccion(u.metadata)}),
        "chunks_en_contexto": sum(len(u.metadata.get("chunk_ids_expandidos", [u.id])) for u in unidades),
        "posiciones_origen": [p for p, _ in r.get("unidades", [])],
        "distancias_top": [round(float(s), 4) for _, s in r.get("pares", [])[:5]],
    }
    registro["fuentes"] = sorted({u.metadata.get("fuente") for u in unidades if u.metadata.get("fuente")})
    registro["caracteres_contexto"] = len(r["contexto"]) if "contexto" in r else None
    registro["caracteres_prompt"] = len(r["prompt"]) if "prompt" in r else None
    mensaje = r.get("mensaje")
    uso = extraer_uso(mensaje) if mensaje is not None else {"estado": "sin_generacion" if not generar else "no_disponible"}
    registro["tokens"] = {
        "generacion": uso,
        "embedding_consulta": {"tokens": None, "estado": "no_reportado_por_el_proveedor"},
    }
    if mensaje is not None:
        texto = texto_de_respuesta(mensaje)
        registro["respuesta"] = {"caracteres": len(texto), "intentos": r.get("intentos_generacion"),
                                 "citas_usadas": sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto)})}
    tarifa_gen = buscar_tarifa(tarifas, registro["modelo_generacion"]) if registro["modelo_generacion"] else None
    tarifa_emb = buscar_tarifa(tarifas, registro["modelo_embeddings"])
    registro["costo_usd"] = desglose_costo(uso, tarifa_gen, pregunta, tarifa_emb) if generar else None
    tarifa_ref = tarifa_gen or tarifa_emb
    registro["tarifas"] = None if tarifa_ref is None else {
        "fuente": tarifa_ref.fuente, "fecha_consulta": tarifa_ref.fecha_consulta, "tipo": tarifa_ref.tipo,
        "generacion": None if tarifa_gen is None else {"entrada": tarifa_gen.entrada, "salida": tarifa_gen.salida},
        "embedding": None if tarifa_emb is None else {"entrada": tarifa_emb.entrada},
    }


def relanzar(registro: dict) -> None:
    """Vuelve a lanzar la excepción capturada (si la hubo) tras guardar el registro."""
    error = registro.pop("_excepcion", None)
    if error is not None:
        raise error


# --- Persistencia ----------------------------------------------------------------------

def guardar_registro(registro: dict, ruta: Path = ARCHIVO_REGISTROS) -> None:
    """Agrega una línea JSON (UTF-8). Nunca reescribe ni borra líneas anteriores."""
    limpio = {k: v for k, v in registro.items() if not k.startswith("_")}
    linea = json.dumps(limpio, ensure_ascii=False, default=str)
    if "\n" in linea:
        raise ValueError("Un registro JSONL no puede contener saltos de línea sin escapar.")
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8", newline="\n") as archivo:
        archivo.write(linea + "\n")


def leer_registros(ruta: Path = ARCHIVO_REGISTROS) -> tuple[list[dict], list[dict]]:
    """Devuelve (registros válidos, errores de lectura con número de línea). No oculta líneas corruptas."""
    ruta = Path(ruta)
    if not ruta.exists():
        return [], []
    registros, errores = [], []
    with ruta.open(encoding="utf-8") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            if not linea.strip():
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError as error:
                errores.append({"linea": numero, "error": str(error)})
                continue
            if not isinstance(dato, dict):
                errores.append({"linea": numero, "error": "la línea no es un objeto JSON"})
                continue
            registros.append(dato)
    return registros, errores


# --- Estadísticas ----------------------------------------------------------------------

def _resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "media": None, "mediana": None, "minimo": None, "maximo": None}
    return {"n": len(valores), "media": statistics.fmean(valores), "mediana": statistics.median(valores),
            "minimo": min(valores), "maximo": max(valores)}


def estadisticas(registros: list[dict], tipo_medicion: str = "real") -> dict:
    """Solo consultas completas ('ok') del tipo indicado; los errores se cuentan aparte."""
    validos = [r for r in registros if r.get("estado") == "ok" and r.get("tipo_medicion") == tipo_medicion]
    etapas = sorted({e for r in validos for e in r.get("tiempos_ms", {})})
    gen = [r["tokens"]["generacion"] for r in validos if r.get("tokens", {}).get("generacion", {}).get("estado") == "reportado"]
    costos = [r["costo_usd"]["total_conocido_usd"] for r in validos
              if r.get("costo_usd") and r["costo_usd"].get("total_conocido_usd") is not None]
    relacion = [r["caracteres_prompt"] / r["tokens"]["generacion"]["entrada"] for r in validos
                if r.get("caracteres_prompt") and r.get("tokens", {}).get("generacion", {}).get("entrada")]
    return {
        "consultas": len(validos),
        "errores": sum(r.get("estado") == "error" for r in registros if r.get("tipo_medicion") == tipo_medicion),
        "total_ms": _resumen([r["tiempo_total_ms"] for r in validos if r.get("tiempo_total_ms") is not None]),
        "sobrecarga_ms": _resumen([r["sobrecarga_ms"] for r in validos if r.get("sobrecarga_ms") is not None]),
        "etapas_ms": {e: _resumen([r["tiempos_ms"][e] for r in validos if r["tiempos_ms"].get(e) is not None])
                      for e in etapas},
        "tokens_entrada": _resumen([g["entrada"] for g in gen if g.get("entrada") is not None]),
        "tokens_salida": _resumen([g["salida"] for g in gen if g.get("salida") is not None]),
        "tokens_razonamiento": _resumen([g["razonamiento"] for g in gen if g.get("razonamiento") is not None]),
        "costo_generacion_usd": _resumen(costos),
        "caracteres_prompt_por_token_entrada": _resumen(relacion),
    }
