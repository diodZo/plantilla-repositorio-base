"""Registro de versiones de prompts (Bloque 32, Misión 1).

Qué se versiona: el material ESTÁTICO del prompt RAG, es decir, la plantilla del mensaje de
sistema y la plantilla del mensaje humano con sus marcadores `{contexto}` y `{pregunta}`. Se unen
en un texto canónico:

    ### system
    <plantilla system>
    ### human
    <plantilla human>

La huella es SHA-256 de ese texto exacto (UTF-8): `huella` = 12 primeros caracteres hex (como en
el curso) y `huella_completa` = los 64. El contexto recuperado y la pregunta son datos dinámicos
de cada consulta y no forman parte de la versión.

Estados: propuesta → activa (solo con una decisión humana aprobada) | rechazada; la activa
anterior pasa a reemplazada. Una propuesta nunca se activa sola.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.gobernanza.almacenamiento_prompts import (
    AlmacenCorruptoError, SecretoEnPromptError, contiene_secreto, guardar_registro, leer_registro, validar_version,
)
from src.rag.configuracion import RAIZ_REPO

NOMBRE_PROMPT_RAG = "prompt_rag"
RUTA_REGISTRO = RAIZ_REPO / "data" / "gobernanza" / "registro_prompts.json"
LONGITUD_HUELLA = 12
ORIGENES_HISTORICOS = ("git",)


class HuellaDesconocidaError(KeyError):
    """No existe ninguna versión con esa huella (o el prefijo es ambiguo)."""


class VersionDuplicadaError(ValueError):
    """Ya existe una versión con el mismo texto (misma huella) para ese nombre."""


class TransicionInvalidaError(ValueError):
    """Cambio de estado no permitido (p. ej., aprobar algo que no está en 'propuesta')."""


def texto_canonico(plantillas: dict[str, str]) -> str:
    if set(plantillas) != {"system", "human"}:
        raise ValueError("Las plantillas deben ser exactamente {'system', 'human'}.")
    return f"### system\n{plantillas['system']}\n### human\n{plantillas['human']}\n"


def huella_completa(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_corta(texto: str) -> str:
    """Huella de 12 caracteres del curso: sha256(texto).hexdigest()[:12]."""
    return huella_completa(texto)[:LONGITUD_HUELLA]


def diff_prompts(texto_a: str, texto_b: str, etiqueta_a: str = "a", etiqueta_b: str = "b") -> str:
    """Diff unificado (difflib.unified_diff) entre dos textos de prompt."""
    return "".join(difflib.unified_diff(texto_a.splitlines(keepends=True), texto_b.splitlines(keepends=True),
                                        fromfile=etiqueta_a, tofile=etiqueta_b))


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validar_decision(decision: Any, aprobado_esperado: bool) -> dict:
    """Una decisión humana: aprobado (bool estricto), revisor, thread_id y origen declarados."""
    if not isinstance(decision, dict):
        raise TransicionInvalidaError("La decisión debe ser un objeto con aprobado, revisor, thread_id y origen.")
    if not isinstance(decision.get("aprobado"), bool) or decision["aprobado"] is not aprobado_esperado:
        raise TransicionInvalidaError(f"La decisión debe tener aprobado={aprobado_esperado} (booleano).")
    for campo in ("revisor", "thread_id", "origen"):
        if not isinstance(decision.get(campo), str) or not decision[campo].strip():
            raise TransicionInvalidaError(f"La decisión necesita '{campo}' (texto no vacío).")
    return {**decision, "fecha": decision.get("fecha") or ahora_iso()}


class RegistroDePrompts:
    """Registro en memoria con persistencia JSON opcional (cada cambio se guarda de forma atómica)."""

    def __init__(self, ruta: Path | str | None = None):
        self.ruta = Path(ruta) if ruta is not None else None
        self._versiones: list[dict] = leer_registro(self.ruta) if self.ruta else []
        self._verificar_integridad()

    # --- consultas -------------------------------------------------------------------------------

    def listar(self, nombre: str | None = None) -> list[dict]:
        return [copy.deepcopy(v) for v in self._versiones if nombre is None or v["nombre"] == nombre]

    def por_huella(self, huella: str) -> dict:
        """Acepta la huella completa o un prefijo de al menos 12 caracteres; debe ser única."""
        if not isinstance(huella, str) or len(huella) < LONGITUD_HUELLA:
            raise HuellaDesconocidaError(f"Huella inválida: {huella!r}.")
        candidatas = [v for v in self._versiones if v["huella_completa"].startswith(huella.lower())]
        if len(candidatas) != 1:
            raise HuellaDesconocidaError(f"Huella {'ambigua' if candidatas else 'inexistente'}: {huella!r}.")
        return copy.deepcopy(candidatas[0])

    def ultima(self, nombre: str = NOMBRE_PROMPT_RAG) -> dict | None:
        versiones = [v for v in self._versiones if v["nombre"] == nombre]
        return copy.deepcopy(max(versiones, key=lambda v: v["version"])) if versiones else None

    def activa(self, nombre: str = NOMBRE_PROMPT_RAG) -> dict | None:
        activas = [v for v in self._versiones if v["nombre"] == nombre and v["estado"] == "activa"]
        return copy.deepcopy(activas[0]) if activas else None

    def texto(self, huella: str) -> str:
        return texto_canonico(self.por_huella(huella)["plantillas"])

    def comparar(self, huella_a: str, huella_b: str) -> str:
        a, b = self.por_huella(huella_a), self.por_huella(huella_b)
        return diff_prompts(texto_canonico(a["plantillas"]), texto_canonico(b["plantillas"]),
                            f"{a['nombre']} v{a['version']} ({a['huella']})", f"{b['nombre']} v{b['version']} ({b['huella']})")

    # --- altas ----------------------------------------------------------------------------------

    def registrar(self, nombre: str, plantillas: dict[str, str], autor: str, nota: str, *, estado: str = "propuesta",
                  fecha: str | None = None, origen: dict | None = None, modelo_validado: str | None = None,
                  parametros_validados: dict | None = None) -> dict:
        """Agrega una versión. Solo se admite estado distinto de 'propuesta' para evidencia histórica de git."""
        origen = origen or {"tipo": "propuesta"}
        if estado != "propuesta" and origen.get("tipo") not in ORIGENES_HISTORICOS:
            raise TransicionInvalidaError("Una versión nueva solo puede registrarse como 'propuesta'; "
                                          "se activa únicamente mediante una aprobación humana.")
        if any(contiene_secreto(t) for t in plantillas.values()):
            raise SecretoEnPromptError("El prompt parece contener una credencial; no se registra.")
        texto = texto_canonico(plantillas)
        completa = huella_completa(texto)
        existente = next((v for v in self._versiones if v["nombre"] == nombre and v["huella_completa"] == completa), None)
        if existente:
            raise VersionDuplicadaError(f"El mismo texto ya está registrado como {nombre} v{existente['version']} "
                                        f"({existente['huella']}, estado {existente['estado']}).")
        if estado == "activa" and self.activa(nombre):
            raise TransicionInvalidaError(f"{nombre} ya tiene una versión activa.")
        version = {
            "nombre": nombre,
            "version": max((v["version"] for v in self._versiones if v["nombre"] == nombre), default=0) + 1,
            "huella": completa[:LONGITUD_HUELLA],
            "huella_completa": completa,
            "autor": autor,
            "fecha": fecha or ahora_iso(),
            "nota": nota,
            "modelo_validado": modelo_validado,
            "parametros_validados": parametros_validados,
            "estado": estado,
            "plantillas": dict(plantillas),
            "origen": dict(origen),
            "decision": None,
        }
        validar_version(version, len(self._versiones))
        self._versiones.append(version)
        self._guardar()
        return copy.deepcopy(version)

    def proponer(self, nombre: str, plantillas: dict[str, str], autor: str, nota: str, **kwargs) -> dict:
        return self.registrar(nombre, plantillas, autor, nota, estado="propuesta", **kwargs)

    # --- transiciones ----------------------------------------------------------------------------

    def _buscar(self, huella: str) -> dict:
        completa = self.por_huella(huella)["huella_completa"]
        return next(v for v in self._versiones if v["huella_completa"] == completa)

    def aprobar(self, huella: str, decision: dict) -> dict:
        """Activa una propuesta con una decisión humana aprobada; la activa anterior pasa a 'reemplazada'."""
        version = self._buscar(huella)
        if version["estado"] != "propuesta":
            raise TransicionInvalidaError(f"Solo se aprueba una 'propuesta'; v{version['version']} está "
                                          f"'{version['estado']}' (¿doble aplicación?).")
        decision = validar_decision(decision, True)
        for otra in self._versiones:
            if otra["nombre"] == version["nombre"] and otra["estado"] == "activa":
                otra["estado"] = "reemplazada"
        version["estado"], version["decision"] = "activa", decision
        self._guardar()
        return copy.deepcopy(version)

    def rechazar(self, huella: str, decision: dict) -> dict:
        version = self._buscar(huella)
        if version["estado"] != "propuesta":
            raise TransicionInvalidaError(f"Solo se rechaza una 'propuesta'; v{version['version']} está '{version['estado']}'.")
        version["estado"], version["decision"] = "rechazada", validar_decision(decision, False)
        self._guardar()
        return copy.deepcopy(version)

    # --- integridad y persistencia -------------------------------------------------------------

    def _verificar_integridad(self) -> None:
        vistos: set[tuple[str, int]] = set()
        for v in self._versiones:
            if huella_completa(texto_canonico(v["plantillas"])) != v["huella_completa"] \
                    or v["huella"] != v["huella_completa"][:LONGITUD_HUELLA]:
                raise AlmacenCorruptoError(f"{v['nombre']} v{v['version']}: la huella no coincide con el texto guardado.")
            if (v["nombre"], v["version"]) in vistos:
                raise AlmacenCorruptoError(f"{v['nombre']} v{v['version']} está duplicada.")
            vistos.add((v["nombre"], v["version"]))
        for nombre in {v["nombre"] for v in self._versiones}:
            if sum(v["nombre"] == nombre and v["estado"] == "activa" for v in self._versiones) > 1:
                raise AlmacenCorruptoError(f"{nombre} tiene más de una versión activa.")

    def _guardar(self) -> None:
        self._verificar_integridad()
        if self.ruta:
            guardar_registro(self.ruta, self._versiones)


# --- Prompts reales del proyecto -----------------------------------------------------------------

# Metadatos tomados de `git log` (comprobados en tests/test_registro_prompts.py).
COMMIT_V1 = {"commit": "08565c9642dc63f7f2ad0b14e2085821a8eb164d", "archivo": "src/rag/prompts.py",
             "autor": "dortiz", "fecha": "2026-11-12T21:53:09-03:00"}
COMMIT_V2 = {"commit": "f5421dc65acc7efef11851909880e4c44121092a", "archivo": "src/rag/seguridad_prompt.py",
             "autor": "dortiz", "fecha": "2026-11-19T22:18:42-03:00"}


def plantillas_bloque26() -> dict[str, str]:
    from src.rag.prompts import INSTRUCCIONES_SISTEMA, PLANTILLA_HUMANO
    return {"system": INSTRUCCIONES_SISTEMA, "human": PLANTILLA_HUMANO}


def plantillas_bloque31() -> dict[str, str]:
    from src.rag.seguridad_prompt import INSTRUCCIONES_SISTEMA_SEGURAS, PLANTILLA_HUMANO_SEGURA
    return {"system": INSTRUCCIONES_SISTEMA_SEGURAS, "human": PLANTILLA_HUMANO_SEGURA}


def crear_registro_historico(ruta: Path | str | None = None) -> RegistroDePrompts:
    """Registro con las dos versiones reales comprobadas en git (v1 Bloque 26, v2 Bloque 31)."""
    registro = RegistroDePrompts(ruta)
    registro.registrar(
        NOMBRE_PROMPT_RAG, plantillas_bloque26(), COMMIT_V1["autor"],
        "Prompt RAG con citas numeradas y contexto delimitado (Bloque 26). Reemplazado en la ruta auditada por v2; "
        "las rutas antiguas (generador.responder, recuperar_corpus, registro_rag, evaluar_bloque27) aún lo envían.",
        estado="reemplazada", fecha=COMMIT_V1["fecha"], origen={"tipo": "git", **{k: COMMIT_V1[k] for k in ("commit", "archivo")}})
    registro.registrar(
        NOMBRE_PROMPT_RAG, plantillas_bloque31(), COMMIT_V2["autor"],
        "Regla 8 (contexto = información no confiable) y aviso en el mensaje humano (Bloque 31). La envía "
        "consultar_auditado. Incorporada por commit; no existe registro de una aprobación formal.",
        estado="activa", fecha=COMMIT_V2["fecha"], origen={"tipo": "git", **{k: COMMIT_V2[k] for k in ("commit", "archivo")}})
    return registro


# --- Identificación del prompt enviado (integración con el Bloque 31) ---------------------------

_cache: dict[tuple, RegistroDePrompts] = {}


def _registro_en_cache(ruta: Path) -> RegistroDePrompts:
    estado = ruta.stat()
    clave = (str(ruta), estado.st_mtime_ns, estado.st_size)
    if clave not in _cache:
        _cache.clear()
        _cache[clave] = RegistroDePrompts(ruta)
    return _cache[clave]


def _patron_humano(plantilla: str) -> re.Pattern:
    partes = re.split(r"\{(\w+)\}", plantilla)
    patron = "".join(re.escape(p) if i % 2 == 0 else r"(.*)" for i, p in enumerate(partes))
    return re.compile(patron, re.DOTALL)


def coincide_con_plantillas(mensajes: list, plantillas: dict[str, str]) -> bool:
    """True si los mensajes ENVIADOS se generaron exactamente con estas plantillas.

    El mensaje de sistema debe ser idéntico; en el humano, todo el texto estático debe coincidir
    carácter a carácter y solo los marcadores pueden contener datos.
    """
    if len(mensajes) != 2 or [getattr(m, "type", None) for m in mensajes] != ["system", "human"]:
        return False
    sistema, humano = (m.content for m in mensajes)
    return (isinstance(sistema, str) and isinstance(humano, str) and sistema == plantillas["system"]
            and _patron_humano(plantillas["human"]).fullmatch(humano) is not None)


def identificar_prompt_enviado(mensajes: list, ruta: Path | str = RUTA_REGISTRO,
                               nombre: str = NOMBRE_PROMPT_RAG) -> dict:
    """Qué versión registrada corresponde al texto REALMENTE enviado. Nunca lanza excepciones.

    Si ninguna coincide, `prompt_registrado=False` y `prompt_version=None`: no se atribuye una
    versión que el generador no usó.
    """
    sistema = next((m.content for m in mensajes if getattr(m, "type", None) == "system"), None)
    resultado = {
        "prompt_nombre": nombre, "prompt_registrado": False, "prompt_version": None, "prompt_huella": None,
        "prompt_estado": None, "prompt_es_activa": False, "prompt_version_activa": None, "prompt_huella_activa": None,
        "prompt_huella_sistema_enviado": huella_corta(sistema) if isinstance(sistema, str) else None,
    }
    try:
        registro = _registro_en_cache(Path(ruta))
    except (OSError, ValueError) as error:  # incluye AlmacenCorruptoError
        resultado["prompt_motivo"] = f"registro_no_disponible: {type(error).__name__}"
        return resultado
    activa = registro.activa(nombre)
    if activa:
        resultado.update(prompt_version_activa=activa["version"], prompt_huella_activa=activa["huella"])
    for version in registro.listar(nombre):
        if coincide_con_plantillas(mensajes, version["plantillas"]):
            resultado.update(prompt_registrado=True, prompt_version=version["version"], prompt_huella=version["huella"],
                             prompt_estado=version["estado"], prompt_es_activa=version["estado"] == "activa")
            return resultado
    resultado["prompt_motivo"] = "texto_enviado_no_coincide_con_ninguna_version"
    return resultado
