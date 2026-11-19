"""Esquema y carga del dataset de personalización (Bloque 29).

Tarea: transformar un mensaje de error técnico del proyecto en un JSON con exactamente
`categoria` y `accion_sugerida`. Cada ejemplo del archivo es {"entrada": str, "salida": str},
donde `salida` es el JSON serializado como texto, igual que lo recibe `types.TuningExample.output`.

Las categorías siguen las clases de error que el código ya distingue:
- red: `ErrorTransitorio` / `TimeoutError` por red o 5xx (`src/cliente.py`, `src/rag/reintentos.py`
  los reintentan con backoff exponencial y jitter).
- autenticacion: 400 API_KEY_INVALID, 401, 403 y clave ausente (`CredencialesInvalidasError`,
  `CredencialesFaltantesError`); el código NUNCA los reintenta.
- cuota: 429. El código lo reintenta igual que un fallo de red, pero la acción humana difiere
  (reducir el ritmo, `--lote` / `--pausa` de `src.indexar_corpus`, revisar el plan).
- entorno: dependencias, permisos de escritura y SQLite (`DependenciaFaltanteError`,
  `DirectorioNoEscribibleError`, chequeo de sqlite3 >= 3.35.0 de chromadb).
- consistencia_indice: errores del índice Chroma (`EmbeddingsIncompatiblesError`,
  `ConfiguracionIncompatibleError`, `ColeccionInexistenteError`, `IndiceVacioError`, `MetadataFaltanteError`).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

RAIZ_REPO = Path(__file__).resolve().parents[2]
DIRECTORIO_DATOS = RAIZ_REPO / "data" / "personalizacion"
RUTA_ENTRENAMIENTO = DIRECTORIO_DATOS / "ejemplos_entrenamiento.json"
RUTA_VALIDACION = DIRECTORIO_DATOS / "ejemplos_validacion.json"

CATEGORIAS: tuple[str, ...] = ("red", "autenticacion", "cuota", "entorno", "consistencia_indice")
CLAVES_SALIDA: tuple[str, ...] = ("categoria", "accion_sugerida")
CLAVES_EJEMPLO: tuple[str, ...] = ("entrada", "salida")
MINIMO_EJEMPLOS_ENTRENAMIENTO = 10  # Mínimo de la actividad del curso, no un requisito de la API.

# Coherencia categoría ↔ acción. Se evalúa sobre el texto normalizado (minúsculas, sin tildes).
# "prohibidos": contradicción evidente (error). "esperados": al menos uno debería aparecer (advertencia).
REGLAS_COHERENCIA: dict[str, dict[str, tuple[str, ...]]] = {
    "red": {
        "esperados": (r"\breintent", r"\bbackoff\b", r"\bconexion\b", r"\bred\b", r"\bdns\b", r"\bproxy\b"),
        "prohibidos": (r"\bapi_key\b", r"\breconstru", r"\binstalar\b"),
    },
    "autenticacion": {
        "esperados": (r"\bapi_key\b", r"\bclave\b", r"\bcredencial", r"\bpermiso", r"\.env\b"),
        # El código nunca reintenta credenciales: "reintentar" solo es válido negado ("no reintentar").
        "prohibidos": (r"(?<!no )\breintentar\b", r"\bbackoff\b", r"\breconstru", r"\binstalar\b"),
    },
    "cuota": {
        "esperados": (r"\bcuota\b", r"\britmo\b", r"\bpausa\b", r"\blote\b", r"\bplan\b", r"\besperar\b"),
        "prohibidos": (r"\bapi_key\b", r"\breconstru", r"\binstalar\b"),
    },
    "entorno": {
        "esperados": (r"\binstalar\b", r"\bpip\b", r"\bpermiso", r"\bsqlite", r"\bentorno\b",
                      r"\bdirectorio\b", r"\bactualizar\b", r"\brequirements"),
        "prohibidos": (r"\bbackoff\b", r"\bcuota\b", r"\bapi_key\b"),
    },
    "consistencia_indice": {
        "esperados": (r"\bindice\b", r"\bindexa", r"\breconstru", r"\bcoleccion\b", r"\bembeddings\b"),
        "prohibidos": (r"\bbackoff\b", r"\bapi_key\b", r"\bcuota\b"),
    },
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados (para comparar y aplicar reglas)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def cargar_ejemplos(ruta: Path | str) -> list[Any]:
    """Lee el archivo JSON tal cual. No valida: la validación completa está en `validacion.py`."""
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if not isinstance(datos, list):
        raise ValueError(f"{ruta} debe contener una lista de ejemplos.")
    return datos


def categoria_de(ejemplo: dict) -> str | None:
    """Categoría del ejemplo si su salida es JSON válido con `categoria` de texto; si no, None."""
    try:
        salida = json.loads(ejemplo["salida"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    valor = salida.get("categoria") if isinstance(salida, dict) else None
    return valor if isinstance(valor, str) else None


def a_tuning_examples(ejemplos: list[dict]) -> list:
    """Convierte ejemplos ya validados en `types.TuningExample` reales del SDK (solo objetos locales)."""
    from google.genai import types

    return [types.TuningExample(text_input=e["entrada"], output=e["salida"]) for e in ejemplos]


def construir_tuning_dataset(ejemplos: list[dict]):
    """`types.TuningDataset` con ejemplos inline. No envía nada a la API."""
    from google.genai import types

    return types.TuningDataset(examples=a_tuning_examples(ejemplos))
