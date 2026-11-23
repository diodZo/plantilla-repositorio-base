"""Persistencia JSON local del registro de prompts y de las solicitudes de aprobación (Bloque 32).

- Escritura atómica: se escribe un archivo temporal en el mismo directorio, se hace `fsync` y se
  reemplaza con `os.replace`. Un corte a mitad de escritura deja intacto el archivo anterior.
- Lectura estricta: JSON inválido o esquema incorrecto lanzan `AlmacenCorruptoError`. El archivo
  corrupto NO se sobrescribe ni se "repara" automáticamente: hay que revisarlo a mano (o restaurarlo
  desde git, porque `data/gobernanza/registro_prompts.json` está versionado).
- Las solicitudes de aprobación se guardan en un archivo SEPARADO del registro de versiones.
- Ningún texto con apariencia de secreto (claves de Google, `api_key=...`) se acepta.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

VERSION_ESQUEMA = 1
ESTADOS_VERSION = ("propuesta", "activa", "rechazada", "reemplazada")
ESTADOS_SOLICITUD = ("pendiente", "aprobada", "rechazada", "error")
CAMPOS_VERSION = {
    "nombre": str, "version": int, "huella": str, "huella_completa": str, "autor": str, "fecha": str, "nota": str,
    "estado": str, "plantillas": dict, "origen": dict,
}
CAMPOS_OPCIONALES_VERSION = ("modelo_validado", "parametros_validados", "decision")
PATRONES_SECRETO = (
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"(api[_-]?key|secret|password|contrase[ñn]a)\s*[:=]\s*\S{8,}", re.IGNORECASE),
)


class AlmacenCorruptoError(ValueError):
    """El archivo existe pero no es JSON válido o no cumple el esquema."""


class SecretoEnPromptError(ValueError):
    """Se intentó guardar un texto que parece contener una credencial."""


def contiene_secreto(texto: str) -> bool:
    return any(p.search(texto) for p in PATRONES_SECRETO)


def escribir_json_atomico(ruta: Path | str, datos: Any) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(datos, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporal = tempfile.mkstemp(prefix=f".{ruta.name}.", suffix=".tmp", dir=ruta.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def _leer(ruta: Path) -> Any:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AlmacenCorruptoError(f"{ruta} no es JSON válido (línea {error.lineno}): no se sobrescribe; "
                                   "revísalo o restáuralo desde git.") from error


def validar_version(datos: dict, posicion: int = 0) -> None:
    donde = f"versión en la posición {posicion}"
    if not isinstance(datos, dict):
        raise AlmacenCorruptoError(f"{donde}: debe ser un objeto.")
    for campo, tipo in CAMPOS_VERSION.items():
        valor = datos.get(campo)
        if isinstance(valor, bool) or not isinstance(valor, tipo):
            raise AlmacenCorruptoError(f"{donde}: '{campo}' falta o no es {tipo.__name__}.")
    desconocidos = set(datos) - set(CAMPOS_VERSION) - set(CAMPOS_OPCIONALES_VERSION)
    if desconocidos:
        raise AlmacenCorruptoError(f"{donde}: campos desconocidos {sorted(desconocidos)}.")
    if datos["estado"] not in ESTADOS_VERSION:
        raise AlmacenCorruptoError(f"{donde}: estado desconocido {datos['estado']!r}.")
    if datos["version"] < 1:
        raise AlmacenCorruptoError(f"{donde}: 'version' debe ser >= 1.")
    plantillas = datos["plantillas"]
    if set(plantillas) != {"system", "human"} or not all(isinstance(v, str) and v for v in plantillas.values()):
        raise AlmacenCorruptoError(f"{donde}: 'plantillas' debe tener 'system' y 'human' de texto no vacío.")
    if any(contiene_secreto(v) for v in plantillas.values()):
        raise SecretoEnPromptError(f"{donde}: la plantilla parece contener una credencial.")


def leer_registro(ruta: Path | str) -> list[dict]:
    """Versiones guardadas (lista vacía si el archivo no existe). Valida el esquema completo."""
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    datos = _leer(ruta)
    if not isinstance(datos, dict) or datos.get("version_esquema") != VERSION_ESQUEMA \
            or not isinstance(datos.get("versiones"), list):
        raise AlmacenCorruptoError(f"{ruta}: se esperaba {{'version_esquema': {VERSION_ESQUEMA}, 'versiones': [...]}}.")
    for posicion, version in enumerate(datos["versiones"]):
        validar_version(version, posicion)
    return datos["versiones"]


def guardar_registro(ruta: Path | str, versiones: list[dict]) -> None:
    for posicion, version in enumerate(versiones):
        validar_version(version, posicion)
    escribir_json_atomico(ruta, {"version_esquema": VERSION_ESQUEMA, "versiones": versiones})


def leer_solicitudes(ruta: Path | str) -> dict[str, dict]:
    """Solicitudes de aprobación por thread_id (persistencia separada del registro)."""
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    datos = _leer(ruta)
    if not isinstance(datos, dict) or not isinstance(datos.get("solicitudes"), dict):
        raise AlmacenCorruptoError(f"{ruta}: se esperaba {{'solicitudes': {{thread_id: {{...}}}}}}.")
    for thread_id, solicitud in datos["solicitudes"].items():
        if not isinstance(solicitud, dict) or solicitud.get("estado") not in ESTADOS_SOLICITUD \
                or not isinstance(solicitud.get("huella"), str):
            raise AlmacenCorruptoError(f"{ruta}: solicitud {thread_id!r} con esquema inválido.")
    return datos["solicitudes"]


def guardar_solicitudes(ruta: Path | str, solicitudes: dict[str, dict]) -> None:
    escribir_json_atomico(ruta, {"solicitudes": solicitudes})
