"""Configuración de tuning construida LOCALMENTE con los tipos reales de google-genai (Bloque 29).

Nada de este módulo contacta la API al importarse ni en sus funciones de construcción.
La única función que podría crear un trabajo real, `crear_trabajo_tuning`, está bloqueada por
defecto y exige tres condiciones explícitas (ver su docstring). Ningún CLI ni test la habilita.

Hallazgos del SDK instalado (google-genai 2.34.0, comprobados con sus conversores locales):
- `TuningDataset.examples` (ejemplos inline) solo se acepta en modo Gemini Developer API (clave de API).
- `tuning_mode` y `adapter_size` (PEFT) solo se aceptan en modo Vertex / "Gemini Enterprise Agent
  Platform"; en ese modo el dataset debe ir como `gcs_uri` (JSONL en Cloud Storage), no inline.
Por tanto, "ejemplos inline + adapter PEFT" no es enviable en ningún modo con este SDK.
"""
from __future__ import annotations

import os
from typing import Any

# Ningún modelo base se ha verificado como compatible con tuning para esta cuenta.
# Para habilitar uno hay que comprobarlo en la documentación oficial y en la cuenta, y añadirlo aquí a mano.
MODELOS_TUNING_VERIFICADOS: frozenset[str] = frozenset()
VARIABLE_AUTORIZACION = "PERSONALIZACION_AUTORIZAR_TUNING"
FRASE_AUTORIZACION = "AUTORIZO_TUNING_CON_COSTO"
GCS_PENDIENTE = "gs://bucket-pendiente/personalizacion/entrenamiento.jsonl"  # Marcador local; no existe.

TIPOS_SDK = ("TuningExample", "TuningDataset", "TuningMode", "AdapterSize", "CreateTuningJobConfig",
             "TuningValidationDataset", "TuningMethod")


class EntrenamientoNoAutorizadoError(RuntimeError):
    """Se intentó crear un trabajo de tuning sin cumplir las condiciones explícitas."""


def info_sdk() -> dict[str, Any]:
    """Versión de google-genai y disponibilidad de los tipos de tuning (introspección local)."""
    try:
        import google.genai as genai
        from google.genai import types
    except ImportError as error:
        return {"instalado": False, "error": str(error)}
    info: dict[str, Any] = {
        "instalado": True,
        "version": getattr(genai, "__version__", "desconocida"),
        "tipos": {nombre: hasattr(types, nombre) for nombre in TIPOS_SDK},
    }
    if hasattr(types, "AdapterSize"):
        info["adapter_sizes"] = [m.name for m in types.AdapterSize]
    if hasattr(types, "TuningMode"):
        info["tuning_modes"] = [m.name for m in types.TuningMode]
    return info


def construir_config_peft(
    nombre_modelo: str = "clasificador-errores-bloque29",
    adapter_size: str = "ADAPTER_SIZE_ONE",
    epoch_count: int | None = None,
):
    """`CreateTuningJobConfig` con PEFT y un adapter pequeño. Solo construye el objeto.

    `epoch_count=None` deja el valor por defecto del servicio: no se inventan hiperparámetros.
    Un adapter pequeño reduce parámetros entrenables; NO garantiza un comportamiento correcto.
    """
    from google.genai import types

    parametros: dict[str, Any] = {
        "tuned_model_display_name": nombre_modelo,
        "tuning_mode": types.TuningMode.TUNING_MODE_PEFT_ADAPTER,
        "adapter_size": types.AdapterSize[adapter_size],
    }
    if epoch_count is not None:
        if epoch_count < 1:
            raise ValueError("epoch_count debe ser >= 1.")
        parametros["epoch_count"] = epoch_count
    return types.CreateTuningJobConfig(**parametros)


def _convertir(modo: str, base_model: str, dataset, config) -> str | None:
    """Pasa los parámetros por el conversor LOCAL del SDK. Devuelve None si los acepta o el motivo del rechazo."""
    from google.genai import tunings, types

    conversor = getattr(tunings, f"_CreateTuningJobParametersPrivate_to_{modo}", None)
    clase = getattr(types, "_CreateTuningJobParametersPrivate", None)
    if conversor is None or clase is None:
        raise LookupError("El SDK instalado no expone los conversores locales esperados.")
    try:
        conversor(clase(base_model=base_model, training_dataset=dataset, config=config))
    except ValueError as error:
        return str(error)
    return None


def verificar_compatibilidad(dataset, config, base_model: str = "modelo-no-verificado") -> dict[str, Any]:
    """Comprueba, sin red, si el SDK aceptaría `dataset` + `config` en cada modo.

    Usa conversores privados del SDK: si una versión futura los cambia, devuelve `verificable=False`
    en lugar de suponer un resultado. "Aceptado" aquí solo significa que el SDK construiría la
    petición; no que la cuenta tenga acceso ni que el modelo admita tuning.
    """
    try:
        return {
            "verificable": True,
            "gemini_developer_api": _convertir("mldev", base_model, dataset, config),
            "vertex": _convertir("vertex", base_model, dataset, config),
        }
    except (LookupError, ImportError, TypeError) as error:
        return {"verificable": False, "motivo": str(error)}


def dataset_gcs_pendiente():
    """`TuningDataset` con un URI de Cloud Storage de marcador (no existe), para comprobar el modo Vertex."""
    from google.genai import types

    return types.TuningDataset(gcs_uri=GCS_PENDIENTE)


def crear_trabajo_tuning(cliente, *, base_model: str, training_dataset, config, autorizacion: str | None = None):
    """Crea un trabajo REAL de tuning (con posible costo). Bloqueado por defecto.

    Exige simultáneamente:
    1. `autorizacion == FRASE_AUTORIZACION` en la llamada.
    2. La variable de entorno `PERSONALIZACION_AUTORIZAR_TUNING` con la misma frase.
    3. `base_model` dentro de `MODELOS_TUNING_VERIFICADOS` (vacío: ningún modelo verificado).
    El cliente se inyecta: este módulo nunca crea un `genai.Client`.
    """
    motivos = []
    if autorizacion != FRASE_AUTORIZACION:
        motivos.append("falta la autorización explícita en la llamada")
    if os.getenv(VARIABLE_AUTORIZACION) != FRASE_AUTORIZACION:
        motivos.append(f"la variable {VARIABLE_AUTORIZACION} no contiene la frase de autorización")
    if base_model not in MODELOS_TUNING_VERIFICADOS:
        motivos.append(f"el modelo base {base_model!r} no está verificado para tuning")
    if cliente is None:
        motivos.append("no se proporcionó un cliente")
    if motivos:
        raise EntrenamientoNoAutorizadoError("Tuning bloqueado: " + "; ".join(motivos) + ".")
    return cliente.tunings.tune(base_model=base_model, training_dataset=training_dataset, config=config)
