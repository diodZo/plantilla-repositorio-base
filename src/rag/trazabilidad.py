"""Correlación por trace_id con `contextvars` (Bloque 31).

El identificador activo vive en un `ContextVar`, no en una variable global: cada hilo y cada
tarea de asyncio ven su propio valor, así que dos consultas concurrentes no se mezclan.
`contexto_traza` lo establece y lo restaura al salir, también si ocurre una excepción.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

TRACE_ID: ContextVar[str | None] = ContextVar("rag_trace_id", default=None)


def nuevo_trace_id() -> str:
    """Identificador aleatorio (UUID4); no deriva de la pregunta ni de datos del usuario."""
    return f"trace-{uuid.uuid4().hex}"


def obtener_trace_id() -> str | None:
    """trace_id activo en el contexto actual, o None fuera de una consulta."""
    return TRACE_ID.get()


@contextmanager
def contexto_traza(trace_id: str | None = None) -> Iterator[str]:
    """Activa un trace_id (nuevo si no se indica) y restaura el anterior al terminar."""
    if trace_id is not None and (not isinstance(trace_id, str) or not trace_id.strip()):
        raise ValueError("trace_id debe ser un texto no vacío.")
    valor = trace_id or nuevo_trace_id()
    token = TRACE_ID.set(valor)
    try:
        yield valor
    finally:
        TRACE_ID.reset(token)
