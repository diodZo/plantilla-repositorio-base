"""Logging estructurado JSON (una línea por evento) para la auditoría del RAG (Bloque 31).

- `JsonFormatter`: ts ISO 8601 en UTC, level, evento, trace_id y datos estructurados; UTF-8
  sin escapar (ensure_ascii=False); los saltos de línea quedan escapados por JSON.
- `sanear`: elimina claves con nombre de secreto y enmascara claves de Google (AIza...).
- `huella`: SHA-256 truncado para correlacionar textos SIN guardarlos. No es anonimización:
  un texto previsible puede recuperarse por diccionario comparando huellas.
- `configurar_logger`: idempotente; no duplica handlers aunque se llame varias veces.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from src.rag.configuracion import RAIZ_REPO
from src.rag.trazabilidad import obtener_trace_id

NOMBRE_LOGGER = "rag.auditoria"
ARCHIVO_AUDITORIA = RAIZ_REPO / "logs" / "rag_auditoria.jsonl"
CLAVES_SECRETAS = re.compile(r"(api[_-]?key|apikey|clave|secret|password|contrasena|token_acceso|authorization)",
                             re.IGNORECASE)
PATRON_CLAVE_GOOGLE = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")
_MARCA_HANDLER = "_rag_auditoria_destino"


def huella(texto: str, longitud: int = 16) -> str:
    """SHA-256 del texto UTF-8, truncado a `longitud` caracteres hexadecimales."""
    if not isinstance(texto, str):
        raise TypeError("huella() espera un texto.")
    if not 8 <= longitud <= 64:
        raise ValueError("longitud debe estar entre 8 y 64.")
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()[:longitud]


def sanear(valor: Any) -> Any:
    """Copia del valor sin claves secretas y con claves de Google enmascaradas."""
    if isinstance(valor, dict):
        return {str(k): ("<oculto>" if CLAVES_SECRETAS.search(str(k)) else sanear(v)) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [sanear(v) for v in valor]
    if isinstance(valor, str):
        return PATRON_CLAVE_GOOGLE.sub("<clave oculta>", valor)
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    return PATRON_CLAVE_GOOGLE.sub("<clave oculta>", str(valor))


class JsonFormatter(logging.Formatter):
    """Formatea cada `LogRecord` como un objeto JSON en una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        datos = getattr(record, "datos", None) or {}
        evento = getattr(record, "evento", None) or record.getMessage()
        trace_id = getattr(record, "trace_id", None) or obtener_trace_id()
        salida: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "evento": evento,
            "trace_id": trace_id,
        }
        for clave, valor in sanear(dict(datos)).items():
            if clave not in salida:  # Los campos base no se pueden sobrescribir desde los datos.
                salida[clave] = valor
        if record.exc_info:
            # Solo el tipo: el mensaje y la traza podrían contener datos sensibles.
            salida["excepcion_tipo"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(salida, ensure_ascii=False, default=str)


def configurar_logger(ruta: Path | str | None = None, stream: TextIO | None = None,
                      nombre: str = NOMBRE_LOGGER, nivel: int = logging.INFO) -> logging.Logger:
    """Logger con JsonFormatter hacia un archivo JSONL (append, UTF-8) y/o un stream.

    Idempotente: si ya existe un handler para el mismo destino, no se agrega otro.
    `propagate=False` evita que el root logger duplique o mezcle los eventos.
    """
    logger = logging.getLogger(nombre)
    logger.setLevel(nivel)
    logger.propagate = False
    existentes = {getattr(h, _MARCA_HANDLER, None) for h in logger.handlers}
    destinos: list[tuple[str, logging.Handler | None]] = []
    if ruta is not None:
        ruta = Path(ruta).resolve()
        clave = f"archivo:{ruta}"
        if clave not in existentes:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            destinos.append((clave, logging.FileHandler(ruta, mode="a", encoding="utf-8")))
    if stream is not None:
        clave = f"stream:{id(stream)}"
        if clave not in existentes:
            destinos.append((clave, logging.StreamHandler(stream)))
    for clave, handler in destinos:
        handler.setFormatter(JsonFormatter())
        setattr(handler, _MARCA_HANDLER, clave)
        logger.addHandler(handler)
    return logger


def cerrar_logger(nombre: str = NOMBRE_LOGGER) -> None:
    """Cierra y quita los handlers (útil en pruebas y al terminar la demostración)."""
    logger = logging.getLogger(nombre)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def registrar_evento(logger: logging.Logger, evento: str, nivel: int = logging.INFO, **datos: Any) -> None:
    """Emite un evento estructurado. Los datos deben ser metadatos, no contenido sensible."""
    logger.log(nivel, evento, extra={"evento": evento, "datos": datos})


def leer_jsonl(ruta: Path | str) -> list[dict]:
    """Lee un archivo JSONL de auditoría (para pruebas y resúmenes)."""
    with open(ruta, encoding="utf-8") as archivo:
        return [json.loads(linea) for linea in archivo if linea.strip()]
