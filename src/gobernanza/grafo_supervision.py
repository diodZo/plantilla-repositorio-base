"""Supervisión humana del despliegue de prompts con LangGraph (Bloque 32, Misión 2).

    START → proponer → solicitar_supervision ──(interrupt)──┐
                             ▲      │                        │ Command(resume=decisión)
                             └──────┤ decisión inválida (≤ MAX_INTENTOS_INVALIDOS)
                                    ├─ aprobada  → aplicar   → END   (activa la nueva huella)
                                    ├─ rechazada → conservar → END   (mantiene la huella anterior)
                                    └─ sin decisión válida   → sin_decision → END (la propuesta sigue sin activar)

Seguridad de la autorización (sin autenticación de aprobadores, que NO está implementada):
- Una decisión válida es un dict con `aprobado` (bool estricto), `revisor`, `huella_revisada` (debe
  coincidir con la propuesta), `origen` declarado y `codigo_confirmacion`. El código se genera al
  iniciar la solicitud, se entrega solo a quien la inicia (la persona que revisa) y en el estado del
  grafo se guarda únicamente su SHA-256. Un `Command(resume=True)` generado por un agente o un modelo
  no es un dict válido ni conoce el código: no aprueba. Es una confirmación de intención, no una
  autenticación.
- Una decisión inválida no lanza excepción dentro del grafo (LangGraph conservaría el valor y lo
  reutilizaría al reintentar): se registra y se vuelve a interrumpir. Error o ausencia ≠ aprobación.
- `GestorSupervision.resolver` valida antes de reanudar: hilo existente, interrupción pendiente,
  hilo no resuelto, huella revisada existente y coincidente, aprobado booleano.

Checkpointer por defecto: `InMemorySaver`. NO es durable: si el proceso termina, las solicitudes
pendientes se pierden (la propuesta queda en 'propuesta', sin activarse: falla de forma segura).
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.gobernanza.almacenamiento_prompts import guardar_solicitudes, leer_solicitudes
from src.gobernanza.registro_prompts import (
    HuellaDesconocidaError, RegistroDePrompts, TransicionInvalidaError, ahora_iso, diff_prompts, texto_canonico,
)

ORIGENES_DECISION = ("humano_cli", "simulada_demo", "simulada_prueba")
CLAVES_DECISION = {"aprobado", "revisor", "huella_revisada", "origen", "codigo_confirmacion"}
MAX_INTENTOS_INVALIDOS = 3
NODO_REVISION = "solicitar_supervision"


class ErrorSupervision(RuntimeError):
    """Base de los errores de la supervisión."""


class SolicitudInexistenteError(ErrorSupervision):
    pass


class SolicitudNoPendienteError(ErrorSupervision):
    pass


class DecisionInvalidaError(ErrorSupervision, ValueError):
    pass


class HuellaNoCoincideError(ErrorSupervision, ValueError):
    pass


class EstadoSupervision(TypedDict, total=False):
    nombre: str
    plantillas: dict
    autor: str
    nota: str
    codigo_hash: str
    huella_propuesta: str
    version_propuesta: int
    huella_anterior: str | None
    diff: str
    decision: dict | None
    intentos_invalidos: int
    ultimo_error: str | None
    resultado: str
    huella_activa_final: str | None


def _hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def validar_decision_humana(valor: Any, estado: dict) -> dict:
    """Valida el valor de reanudación. Lanza DecisionInvalidaError con el motivo."""
    if not isinstance(valor, dict):
        raise DecisionInvalidaError(f"La decisión debe ser un objeto, no {type(valor).__name__}.")
    if set(valor) != CLAVES_DECISION:
        raise DecisionInvalidaError(f"La decisión debe tener exactamente {sorted(CLAVES_DECISION)}.")
    if not isinstance(valor["aprobado"], bool):
        raise DecisionInvalidaError(f"'aprobado' debe ser booleano; se recibió {valor['aprobado']!r}.")
    if not isinstance(valor["revisor"], str) or not valor["revisor"].strip():
        raise DecisionInvalidaError("Falta 'revisor'.")
    if valor["origen"] not in ORIGENES_DECISION:
        raise DecisionInvalidaError(f"Origen no permitido: {valor['origen']!r}.")
    huella = valor["huella_revisada"]
    if not isinstance(huella, str) or len(huella) < 12 or not estado["huella_propuesta"].startswith(huella):
        raise DecisionInvalidaError("La huella revisada no coincide con la propuesta pendiente.")
    codigo = valor["codigo_confirmacion"]
    if not isinstance(codigo, str) or not secrets.compare_digest(_hash_codigo(codigo), estado["codigo_hash"]):
        raise DecisionInvalidaError("Código de confirmación incorrecto.")
    return {"aprobado": valor["aprobado"], "revisor": valor["revisor"].strip(), "origen": valor["origen"]}


def construir_grafo(registro: RegistroDePrompts, checkpointer=None):
    """Compila el grafo. El registro se inyecta por closure (no se guarda en el estado)."""

    def proponer(estado: EstadoSupervision) -> dict:
        anterior = registro.activa(estado["nombre"])
        nueva = registro.proponer(estado["nombre"], estado["plantillas"], estado["autor"], estado["nota"])
        diff = (registro.comparar(anterior["huella_completa"], nueva["huella_completa"]) if anterior
                else diff_prompts("", texto_canonico(nueva["plantillas"]), "(sin versión activa)", nueva["huella"]))
        return {"huella_propuesta": nueva["huella_completa"], "version_propuesta": nueva["version"],
                "huella_anterior": anterior["huella_completa"] if anterior else None, "diff": diff,
                "intentos_invalidos": 0, "ultimo_error": None, "decision": None}

    def solicitar_supervision(estado: EstadoSupervision) -> dict:
        # Sin efectos laterales antes de interrupt(): LangGraph vuelve a ejecutar este nodo al reanudar.
        valor = interrupt({
            "tipo": "aprobacion_prompt",
            "nombre": estado["nombre"],
            "version_propuesta": estado["version_propuesta"],
            "huella_propuesta": estado["huella_propuesta"],
            "huella_anterior": estado["huella_anterior"],
            "autor": estado["autor"],
            "nota": estado["nota"],
            "diff": estado["diff"],
            "intentos_invalidos": estado.get("intentos_invalidos", 0),
            "ultimo_error": estado.get("ultimo_error"),
        })
        try:
            return {"decision": validar_decision_humana(valor, estado), "ultimo_error": None}
        except DecisionInvalidaError as error:
            return {"decision": None, "intentos_invalidos": estado.get("intentos_invalidos", 0) + 1,
                    "ultimo_error": str(error)}

    def ruta(estado: EstadoSupervision) -> str:
        decision = estado.get("decision")
        if decision is None:
            return NODO_REVISION if estado.get("intentos_invalidos", 0) < MAX_INTENTOS_INVALIDOS else "sin_decision"
        return "aplicar" if decision["aprobado"] is True else "conservar"

    def _decision_registrable(estado: EstadoSupervision, config) -> dict:
        return {**estado["decision"], "thread_id": config["configurable"]["thread_id"], "fecha": ahora_iso()}

    def aplicar(estado: EstadoSupervision, config) -> dict:
        actual = registro.activa(estado["nombre"])
        if (actual["huella_completa"] if actual else None) != estado["huella_anterior"]:
            raise TransicionInvalidaError("La versión activa cambió desde que se hizo la propuesta; no se aplica.")
        activada = registro.aprobar(estado["huella_propuesta"], _decision_registrable(estado, config))
        return {"resultado": "activada", "huella_activa_final": activada["huella_completa"]}

    def conservar(estado: EstadoSupervision, config) -> dict:
        registro.rechazar(estado["huella_propuesta"], _decision_registrable(estado, config))
        actual = registro.activa(estado["nombre"])
        return {"resultado": "rechazada_se_mantiene_anterior",
                "huella_activa_final": actual["huella_completa"] if actual else None}

    def sin_decision(estado: EstadoSupervision) -> dict:
        actual = registro.activa(estado["nombre"])
        return {"resultado": "sin_decision_valida_no_se_activa",
                "huella_activa_final": actual["huella_completa"] if actual else None}

    grafo = StateGraph(EstadoSupervision)
    grafo.add_node("proponer", proponer)
    grafo.add_node(NODO_REVISION, solicitar_supervision)
    grafo.add_node("aplicar", aplicar)
    grafo.add_node("conservar", conservar)
    grafo.add_node("sin_decision", sin_decision)
    grafo.add_edge(START, "proponer")
    grafo.add_edge("proponer", NODO_REVISION)
    grafo.add_conditional_edges(NODO_REVISION, ruta, [NODO_REVISION, "aplicar", "conservar", "sin_decision"])
    for final in ("aplicar", "conservar", "sin_decision"):
        grafo.add_edge(final, END)
    return grafo.compile(checkpointer=checkpointer if checkpointer is not None else InMemorySaver())


class GestorSupervision:
    """Punto de entrada recomendado: crea solicitudes y las resuelve con validaciones previas."""

    def __init__(self, registro: RegistroDePrompts, checkpointer=None, ruta_solicitudes: Path | str | None = None):
        self.registro = registro
        self.grafo = construir_grafo(registro, checkpointer)
        self.ruta_solicitudes = Path(ruta_solicitudes) if ruta_solicitudes else None
        self.solicitudes = leer_solicitudes(self.ruta_solicitudes) if self.ruta_solicitudes else {}

    @staticmethod
    def config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _guardar(self) -> None:
        if self.ruta_solicitudes:
            guardar_solicitudes(self.ruta_solicitudes, self.solicitudes)

    def iniciar(self, nombre: str, plantillas: dict, autor: str, nota: str) -> dict:
        """Registra la propuesta y ejecuta hasta el interrupt. Devuelve thread_id, código y lo pendiente.

        El código de confirmación se devuelve SOLO aquí: debe mostrarse a la persona que revisa.
        """
        thread_id = f"aprobacion-{uuid.uuid4().hex}"
        if thread_id in self.solicitudes or self.grafo.get_state(self.config(thread_id)).values:
            raise ErrorSupervision("thread_id repetido; no se reutilizan hilos.")
        codigo = secrets.token_hex(4)
        self.grafo.invoke({"nombre": nombre, "plantillas": plantillas, "autor": autor, "nota": nota,
                           "codigo_hash": _hash_codigo(codigo)}, self.config(thread_id))
        pendiente = self.pendiente(thread_id)
        self.solicitudes[thread_id] = {"huella": pendiente["huella_propuesta"], "estado": "pendiente",
                                       "creada": ahora_iso(), "nombre": nombre}
        self._guardar()
        return {"thread_id": thread_id, "codigo_confirmacion": codigo, "pendiente": pendiente}

    def pendiente(self, thread_id: str) -> dict:
        """Lee con get_state la interrupción pendiente. Error si el hilo no existe o no está pendiente."""
        estado = self.grafo.get_state(self.config(thread_id))
        if not estado.values:
            raise SolicitudInexistenteError(f"No existe el hilo {thread_id!r} en este checkpointer.")
        if estado.next != (NODO_REVISION,) or not estado.interrupts:
            raise SolicitudNoPendienteError(f"El hilo {thread_id!r} no tiene una interrupción pendiente "
                                            f"(resultado: {estado.values.get('resultado')!r}).")
        return estado.interrupts[0].value

    def resolver(self, thread_id: str, *, aprobado: Any, revisor: str, huella_revisada: str,
                 codigo_confirmacion: str, origen: str) -> dict:
        if not isinstance(aprobado, bool):
            raise DecisionInvalidaError(f"'aprobado' debe ser booleano; se recibió {aprobado!r}.")
        if self.solicitudes.get(thread_id, {}).get("estado", "pendiente") != "pendiente":
            raise SolicitudNoPendienteError(f"El hilo {thread_id!r} ya fue resuelto; no se reutiliza.")
        pendiente = self.pendiente(thread_id)
        try:
            self.registro.por_huella(huella_revisada)
        except HuellaDesconocidaError as error:
            raise HuellaNoCoincideError(f"La huella revisada no existe en el registro: {huella_revisada!r}.") from error
        if not pendiente["huella_propuesta"].startswith(huella_revisada):
            raise HuellaNoCoincideError("La huella revisada no es la de la propuesta pendiente.")
        decision = {"aprobado": aprobado, "revisor": revisor, "huella_revisada": huella_revisada,
                    "origen": origen, "codigo_confirmacion": codigo_confirmacion}
        self.grafo.invoke(Command(resume=decision), self.config(thread_id))
        estado = self.grafo.get_state(self.config(thread_id))
        if estado.next:  # La decisión fue inválida dentro del grafo: sigue pendiente (o se cerró sin decisión).
            raise DecisionInvalidaError(f"Decisión rechazada por el grafo: {estado.values.get('ultimo_error')}")
        resultado = estado.values["resultado"]
        self.solicitudes[thread_id]["estado"] = ("aprobada" if resultado == "activada" else
                                                 "rechazada" if resultado.startswith("rechazada") else "error")
        self.solicitudes[thread_id]["resuelta"] = ahora_iso()
        self._guardar()
        return dict(estado.values)

    def huerfanas(self) -> list[str]:
        """Solicitudes 'pendiente' cuyo hilo ya no existe en el checkpointer (p. ej., tras reiniciar)."""
        return [t for t, s in self.solicitudes.items()
                if s["estado"] == "pendiente" and not self.grafo.get_state(self.config(t)).values]
