"""Servicio RAG integrado (Gate 2): un único punto de entrada con todas las defensas.

Flujo (reutiliza los Bloques 24–32; no es una segunda implementación):
  consulta → trace_id → índice persistente (cargar_indice, sin reindexar) → 1 embed_query
  → búsqueda Chroma → expansión small-to-big → filtro de inyección sobre unidades finales
  → citas reconstruidas → prompt con roles (versión identificada) → generación
  → validación de citas o abstención → respuesta + auditoría JSONL + consumo
Las etapas hasta la generación son `rag.auditoria.consultar_auditado` (Bloque 31/32); este
módulo agrega la preparación incremental del índice, la validación final de citas y el contrato.

Modos:
  DEMO (predeterminado): corpus sintético, índice Chroma en un directorio temporal, embeddings
       simulados y un modelo falso que responde con el fragmento [1]. Sin clave de API ni red.
  REAL (`--real`): índice existente (CONFIG_BLOQUE26_MD) y Gemini. Ejecuta el preflight antes de
       cualquier llamada y NUNCA indexa. No se ejecuta en pruebas ni demostraciones.

RUTAS HEREDADAS (no recomendadas: omiten el filtro de inyección, la auditoría y la identificación
del prompt): `rag.generador.responder`, `python -m src.recuperar_corpus`, `python -m src.registro_rag`
y `python -m src.evaluar_bloque27`. Se conservan por compatibilidad con los Bloques 26–28.

Uso:
  python -m src.servicio_rag                         # demo
  python -m src.servicio_rag --pregunta "¿...?"      # demo con otra pregunta
  python -m src.servicio_rag --real --pregunta "¿...?"   # OPTATIVO: usa Gemini (con costo posible)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from src.logging_rag import DOCUMENTOS_DEMO, EmbeddingsDemo
from src.rag.auditoria import RESPUESTA_TODO_DESCARTADO, consultar_auditado
from src.rag.chunking import dividir_documentos
from src.rag.configuracion import ConfiguracionIndice
from src.rag.embeddings import EmbeddingsConReintentos
from src.rag.fundamentacion import decidir, evaluar_fundamentacion
from src.rag.generador import RESPUESTA_SIN_CONTEXTO
from src.rag.indexador import cargar_indice, contar_chunks, indexar, planificar_indexacion
from src.rag.logging_json import cerrar_logger, configurar_logger, registrar_evento
from src.rag.trazabilidad import contexto_traza

RUTAS_HEREDADAS = ("src.rag.generador.responder", "src.recuperar_corpus", "src.registro_rag", "src.evaluar_bloque27")
MODELO_EMBEDDINGS_DEMO = "simulado/bolsa-de-palabras"
MODELO_GENERACION_DEMO = "simulado/modelo-falso"
RESPUESTA_CITAS_INVALIDAS = ("La respuesta generada no pudo validarse contra las fuentes recuperadas; "
                             "se omite para no presentar afirmaciones sin respaldo.")
RESPUESTA_FUENTE_NO_PERTINENTE = ("Las fuentes recuperadas no parecen tratar la pregunta; no hay información "
                                  "suficiente para responder con respaldo.")
MARCA_ABSTENCION_MODELO = "no contiene información suficiente"
PREGUNTA_DEMO = "¿En qué plazo puedo devolver un producto?"

CORPUS_DEMO: list[Document] = [
    *DOCUMENTOS_DEMO,
    Document(page_content=(
        "# Envíos\n\n## Plazos de entrega\n\n"
        "Los pedidos se despachan en un máximo de 48 horas hábiles. "
        "La entrega en regiones demora entre 3 y 5 días hábiles."),
        metadata={"fuente": "demo/envios.md", "documento_id": "demo-envios"}),
    Document(page_content=(
        "# Garantía\n\n## Cobertura\n\n"
        "La garantía legal cubre fallas de fabricación durante 6 meses desde la compra. "
        "No cubre daños por mal uso."),
        metadata={"fuente": "demo/garantia.md", "documento_id": "demo-garantia"}),
]


@dataclass
class RespuestaServicio:
    """Contrato de respuesta del servicio. Los valores provienen de la ejecución, nunca se rellenan."""

    respuesta: str
    fuentes: list[dict]
    trace_id: str
    estado: str            # respondida | abstencion | rechazada_citas_invalidas | rechazada_sin_citas
    motivo: str | None
    modo: str              # simulado | real
    prompt_version: int | None
    prompt_huella: str | None
    tokens: dict
    medicion: str          # simulada | real | sin_generacion
    tiempo_total_ms: float | None
    costo_estimado_usd: float | None
    fuentes_contexto: list[dict] = field(default_factory=list)
    unidades_descartadas: int = 0
    fundamentacion: dict | None = None  # Señales heurísticas (no semánticas); None si no hubo respuesta que evaluar.

    def como_dict(self) -> dict:
        return asdict(self)


class ModeloSimulado:
    """SIMULACIÓN: responde con la primera oración del fragmento [1] del contexto y la cita [1].

    No es un LLM. Sus tokens son una aproximación (caracteres/4) marcada como `simulada` en la
    auditoría. Sirve para ensayar el servicio completo sin red.
    """

    def __init__(self, uso: bool = True):
        self.uso = uso
        self.llamadas = 0

    def invoke(self, mensajes, config=None) -> AIMessage:
        self.llamadas += 1
        humano = str(mensajes[-1].content)
        contexto = humano.split("<contexto>", 1)[-1].split("</contexto>", 1)[0]
        fragmento = re.search(r"\[1\]\s*(?:\[[^\]\n]*\]\s*)?(.+?)(?:\n\n\[\d+\]|\Z)", contexto, re.DOTALL)
        if fragmento:
            oracion = re.split(r"(?<=\.)\s", fragmento.group(1).strip(), maxsplit=1)[0]
            texto = f"[SIMULADO] Según la documentación: {oracion} [1]"
        else:
            texto = "[SIMULADO] La documentación proporcionada no contiene información suficiente para responder."
        caracteres = sum(len(str(m.content)) for m in mensajes)
        uso = ({"input_tokens": caracteres // 4, "output_tokens": len(texto) // 4,
                "total_tokens": caracteres // 4 + len(texto) // 4} if self.uso else None)
        return AIMessage(content=texto, usage_metadata=uso)


def preparar_indice(documentos: list[Document], config: ConfiguracionIndice, embeddings,
                    podar_huerfanos: bool = False) -> dict:
    """Crea el índice si no existe, lo reutiliza si no hay cambios o agrega solo lo nuevo (Bloques 24–25).

    No se llama al consultar: la consulta solo carga el índice existente.
    """
    chunks = dividir_documentos(documentos, config.estrategia, config.chunk_size, config.chunk_overlap)
    plan = planificar_indexacion(chunks, config)  # también valida la compatibilidad de embeddings
    if plan["coleccion_existe"] and not plan["nuevos"] and not (podar_huerfanos and plan["huerfanos"]):
        return {"accion": "reutilizado", "chunks_corpus": len(chunks), "agregados": 0,
                "huerfanos": len(plan["huerfanos"]), "podados": 0, "conteo": contar_chunks(config)}
    resultado = indexar(chunks, config, embeddings, podar_huerfanos=podar_huerfanos)
    return {"accion": "actualizado" if plan["coleccion_existe"] else "creado", "chunks_corpus": len(chunks),
            "agregados": resultado.agregados, "huerfanos": len(resultado.huerfanos), "podados": resultado.podados,
            "conteo": resultado.conteo_final}


class ServicioRAG:
    """Servicio RAG con defensas obligatorias. Única ruta recomendada para generar respuestas."""

    def __init__(self, almacen, embeddings, modelo, logger: logging.Logger, *, modo: str, modelo_generacion: str,
                 modelo_embeddings: str, tarifas: dict | None = None, k: int = 3, expandir: bool = True):
        if modo not in ("simulado", "real"):
            raise ValueError("modo debe ser 'simulado' o 'real'.")
        self.almacen, self.embeddings, self.modelo, self.logger = almacen, embeddings, modelo, logger
        self.modo, self.modelo_generacion, self.modelo_embeddings = modo, modelo_generacion, modelo_embeddings
        self.tarifas, self.k, self.expandir = tarifas, k, expandir

    def consultar(self, pregunta: str, callbacks: list | None = None) -> RespuestaServicio:
        resultado = consultar_auditado(
            self.almacen, self.embeddings, self.modelo, pregunta, logger=self.logger,
            modelo_generacion=self.modelo_generacion, modelo_embeddings=self.modelo_embeddings,
            tipo_medicion="simulada" if self.modo == "simulado" else "real", tarifas=self.tarifas,
            k=self.k, expandir=self.expandir, callbacks=callbacks)
        fuentes_contexto = [{"numero": n, "documento": f} for n, f in sorted(resultado.citas.items())]
        estado, motivo, texto, fuentes, senales = self._validar(resultado, pregunta)
        consumo = resultado.consumo or {}
        respuesta = RespuestaServicio(
            respuesta=texto, fuentes=fuentes, trace_id=resultado.trace_id, estado=estado, motivo=motivo,
            modo=self.modo, prompt_version=(resultado.prompt or {}).get("prompt_version"),
            prompt_huella=(resultado.prompt or {}).get("prompt_huella"),
            tokens={k: consumo.get(k) for k in ("input_tokens", "output_tokens", "total_tokens")},
            medicion=consumo.get("tipo_medicion", "sin_generacion"),
            tiempo_total_ms=resultado.tiempos.get("tiempo_total_ms"),
            costo_estimado_usd=consumo.get("costo_estimado_usd"), fuentes_contexto=fuentes_contexto,
            unidades_descartadas=len(resultado.descartadas), fundamentacion=senales)
        with contexto_traza(resultado.trace_id):  # mismo trace_id que el resto de la consulta
            nivel = logging.INFO if estado == "respondida" else logging.WARNING
            registrar_evento(self.logger, "respuesta_servicio", nivel, estado=estado, motivo=motivo, modo=self.modo,
                             fuentes_citadas=[f["documento"] for f in fuentes],
                             prompt_version=respuesta.prompt_version, fundamentacion=senales)
        return respuesta

    @staticmethod
    def _validar(resultado, pregunta: str) -> tuple[str, str | None, str, list[dict], dict | None]:
        """Validación final, de lo exacto a lo heurístico. Solo se entrega una respuesta factual si
        sus citas existen y las señales léxicas de relevancia y respaldo no la contradicen."""
        if resultado.estado == "abstencion":
            motivo = "contexto_comprometido" if resultado.descartadas else "sin_contexto"
            return "abstencion", motivo, resultado.respuesta, [], None
        if MARCA_ABSTENCION_MODELO in resultado.respuesta.lower():
            return "abstencion", "modelo_sin_informacion", resultado.respuesta, [], None
        if resultado.metricas.get("citas_invalidas"):  # 1. estructural (exacta)
            return "rechazada_citas_invalidas", f"citas inexistentes {resultado.metricas['citas_invalidas']}", \
                RESPUESTA_CITAS_INVALIDAS, [], None
        usadas = resultado.metricas.get("citas_usadas", [])
        if not usadas:
            return "rechazada_sin_citas", "la respuesta no cita ninguna fuente", RESPUESTA_CITAS_INVALIDAS, [], None
        senales = evaluar_fundamentacion(pregunta, resultado.respuesta, resultado.textos_citas)  # 2-3. heurísticas
        decision = decidir(senales)
        if decision:
            estado, motivo = decision
            texto = RESPUESTA_FUENTE_NO_PERTINENTE if estado == "abstencion" else RESPUESTA_CITAS_INVALIDAS
            return estado, motivo, texto, [], senales
        return ("respondida", None, resultado.respuesta,
                [{"numero": n, "documento": resultado.citas[n]} for n in usadas], senales)


def cerrar_servicio(nombre_logger: str | None = None) -> None:
    """Cierra el logger y libera los clientes de Chroma (en Windows retienen los archivos del índice)."""
    import gc

    from chromadb.api.client import SharedSystemClient

    if nombre_logger:
        cerrar_logger(nombre_logger)
    SharedSystemClient.clear_system_cache()
    gc.collect()


def config_demo(directorio: Path) -> ConfiguracionIndice:
    return ConfiguracionIndice(nombre_coleccion="gate2_demo", directorio=Path(directorio).resolve() / "indice",
                               chunk_size=160, chunk_overlap=20, estrategia="markdown",
                               modelo_embeddings=MODELO_EMBEDDINGS_DEMO)


def crear_servicio_demo(directorio: Path, documentos: list[Document] | None = None, nombre_logger: str | None = None,
                        modelo=None) -> tuple[ServicioRAG, dict]:
    """Servicio DEMO en `directorio` (temporal): índice Chroma, logs y embeddings simulados."""
    directorio = Path(directorio)
    config = config_demo(directorio)
    embeddings = EmbeddingsConReintentos(EmbeddingsDemo())
    indice = preparar_indice(documentos or CORPUS_DEMO, config, embeddings)
    logger = configurar_logger(ruta=directorio / "logs" / "rag_auditoria.jsonl",
                               nombre=nombre_logger or f"gate2.demo.{id(directorio)}")
    servicio = ServicioRAG(cargar_indice(config, embeddings), embeddings, modelo or ModeloSimulado(), logger,
                           modo="simulado", modelo_generacion=MODELO_GENERACION_DEMO,
                           modelo_embeddings=MODELO_EMBEDDINGS_DEMO, tarifas=None)
    return servicio, indice


def crear_servicio_real(k: int = 3) -> ServicioRAG:  # pragma: no cover - requiere Gemini; no se ejecuta en pruebas
    """Servicio REAL: preflight primero; luego índice existente y Gemini. Nunca indexa."""
    from src.rag.configuracion import CONFIG_BLOQUE26_MD, MODELO_EMBEDDINGS, obtener_modelo_chat
    from src.rag.costos import cargar_tarifas
    from src.rag.embeddings import crear_embeddings_gemini
    from src.rag.generador import crear_modelo_chat
    from src.rag.logging_json import ARCHIVO_AUDITORIA
    from src.rag.preflight import ERROR, ejecutar_preflight

    errores = [r for r in ejecutar_preflight() if r.nivel == ERROR]
    if errores:
        raise RuntimeError("Preflight con errores; no se llama a Gemini: "
                           + "; ".join(f"{r.comprobacion}: {r.mensaje}" for r in errores))
    embeddings = EmbeddingsConReintentos(crear_embeddings_gemini())
    return ServicioRAG(cargar_indice(CONFIG_BLOQUE26_MD, embeddings), embeddings, crear_modelo_chat(),
                       configurar_logger(ruta=ARCHIVO_AUDITORIA), modo="real", modelo_generacion=obtener_modelo_chat(),
                       modelo_embeddings=MODELO_EMBEDDINGS, tarifas=cargar_tarifas(), k=k)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pregunta", default=None)
    parser.add_argument("--real", action="store_true", help="OPTATIVO: usa Gemini y el índice real (posible costo)")
    args = parser.parse_args(argv)

    if args.real:  # pragma: no cover - modo real no se ejecuta en pruebas
        if not args.pregunta:
            parser.error("--real exige --pregunta.")
        servicio = crear_servicio_real()
        try:
            print(json.dumps(servicio.consultar(args.pregunta).como_dict(), ensure_ascii=False, indent=2))
        finally:
            cerrar_logger()
        return 0

    with tempfile.TemporaryDirectory(prefix="servicio_rag_demo_") as directorio:
        nombre = "gate2.servicio_cli"
        try:
            servicio, indice = crear_servicio_demo(Path(directorio), nombre_logger=nombre)
            print(f"Modo DEMO (simulado, sin Gemini). Índice temporal: {indice['accion']} "
                  f"({indice['conteo']} chunks).")
            print(json.dumps(servicio.consultar(args.pregunta or PREGUNTA_DEMO).como_dict(), ensure_ascii=False, indent=2))
            del servicio
        finally:
            cerrar_servicio(nombre)
    return 0


if __name__ == "__main__":
    sys.exit(main())
