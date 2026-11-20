"""Callback de LangChain para auditoría (Bloque 31).

Firmas verificadas en langchain-core 1.7.4 (`BaseCallbackHandler`):
  on_retriever_start(serialized, query, *, run_id, parent_run_id=None, tags=None, metadata=None, **kw)
  on_retriever_end(documents, *, run_id, parent_run_id=None, **kw)
  on_retriever_error(error, *, run_id, parent_run_id=None, **kw)
  on_llm_start(serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kw)
  on_chat_model_start(serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kw)
  on_llm_end(response: LLMResult, *, run_id, parent_run_id=None, tags=None, **kw)
  on_llm_error(error, *, run_id, parent_run_id=None, tags=None, **kw)

Por defecto NO guarda el texto de la consulta, del prompt ni de los documentos: solo longitudes,
conteos, fuentes, tokens y el tipo de error. Un fallo al auditar nunca interrumpe la cadena
(`raise_error=False` y cada método atrapa sus propias excepciones).
"""
from __future__ import annotations

import logging
from typing import Any, Sequence
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from src.rag.logging_json import registrar_evento


def _texto_mensaje(mensaje: Any) -> str:
    contenido = getattr(mensaje, "content", "")
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in contenido)
    return str(contenido)


def tokens_de_llm_result(response: Any) -> dict[str, int | None]:
    """Tokens desde `usage_metadata` del mensaje (chat) o `llm_output['token_usage']`; None si no hay."""
    for lista in getattr(response, "generations", None) or []:
        for generacion in lista:
            uso = getattr(getattr(generacion, "message", None), "usage_metadata", None)
            if uso:
                return {"input_tokens": uso.get("input_tokens"), "output_tokens": uso.get("output_tokens"),
                        "total_tokens": uso.get("total_tokens")}
    uso = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}
    return {"input_tokens": uso.get("prompt_tokens"), "output_tokens": uso.get("completion_tokens"),
            "total_tokens": uso.get("total_tokens")}


class ManejadorAuditoria(BaseCallbackHandler):
    """Registra eventos de LangChain con run_id, parent_run_id y el trace_id activo (vía JsonFormatter)."""

    raise_error = False

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.errores_internos = 0

    def _emitir(self, evento: str, run_id: UUID, parent_run_id: UUID | None, nivel: int = logging.INFO,
                **datos: Any) -> None:
        try:
            registrar_evento(self.logger, evento, nivel, run_id=str(run_id),
                             parent_run_id=str(parent_run_id) if parent_run_id else None, **datos)
        except Exception:  # La auditoría no debe romper la consulta; se cuenta para poder detectarlo.
            self.errores_internos += 1

    def on_retriever_start(self, serialized: dict[str, Any], query: str, *, run_id: UUID,
                           parent_run_id: UUID | None = None, tags: list[str] | None = None,
                           metadata: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._emitir("lc_retriever_start", run_id, parent_run_id, consulta_len=len(query or ""))

    def on_retriever_end(self, documents: Sequence[Any], *, run_id: UUID, parent_run_id: UUID | None = None,
                         **kwargs: Any) -> None:
        fuentes = sorted({d.metadata.get("fuente") for d in documents if getattr(d, "metadata", {}).get("fuente")})
        self._emitir("lc_retriever_end", run_id, parent_run_id, documentos=len(documents), fuentes=fuentes)

    def on_retriever_error(self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None,
                           **kwargs: Any) -> None:
        self._emitir("lc_retriever_error", run_id, parent_run_id, logging.ERROR, error_tipo=type(error).__name__)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, run_id: UUID,
                     parent_run_id: UUID | None = None, tags: list[str] | None = None,
                     metadata: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._emitir("lc_llm_start", run_id, parent_run_id, prompts=len(prompts),
                     prompt_caracteres=sum(len(p) for p in prompts))

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: UUID,
                            parent_run_id: UUID | None = None, tags: list[str] | None = None,
                            metadata: dict[str, Any] | None = None, **kwargs: Any) -> None:
        mensajes = [m for lista in messages for m in lista]
        self._emitir("lc_chat_model_start", run_id, parent_run_id, mensajes=len(mensajes),
                     roles=[getattr(m, "type", "?") for m in mensajes],
                     prompt_caracteres=sum(len(_texto_mensaje(m)) for m in mensajes))

    def on_llm_end(self, response: Any, *, run_id: UUID, parent_run_id: UUID | None = None,
                   tags: list[str] | None = None, **kwargs: Any) -> None:
        textos = [getattr(g, "text", "") or _texto_mensaje(getattr(g, "message", None))
                  for lista in (getattr(response, "generations", None) or []) for g in lista]
        self._emitir("lc_llm_end", run_id, parent_run_id, respuesta_caracteres=sum(len(t) for t in textos),
                     **tokens_de_llm_result(response))

    def on_llm_error(self, error: BaseException, *, run_id: UUID, parent_run_id: UUID | None = None,
                     tags: list[str] | None = None, **kwargs: Any) -> None:
        self._emitir("lc_llm_error", run_id, parent_run_id, logging.ERROR, error_tipo=type(error).__name__)
