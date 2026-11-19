"""Bloque 29: dataset real, conversión a tipos del SDK, configuración PEFT local y bloqueo del tuning.

Todo offline: ninguna prueba crea un cliente de Gemini ni llama a la API.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from src.personalizacion import configuracion_tuning as ct
from src.personalizacion.balance import chequear_balance
from src.personalizacion.dataset import (
    CATEGORIAS, CLAVES_SALIDA, MINIMO_EJEMPLOS_ENTRENAMIENTO, RAIZ_REPO, RUTA_ENTRENAMIENTO, RUTA_VALIDACION,
    a_tuning_examples, cargar_ejemplos, construir_tuning_dataset,
)
from src.personalizacion.validacion import errores, solapamiento, validar_dataset

types = pytest.importorskip("google.genai.types")


@pytest.fixture(scope="module")
def entrenamiento():
    return cargar_ejemplos(RUTA_ENTRENAMIENTO)


@pytest.fixture(scope="module")
def validacion():
    return cargar_ejemplos(RUTA_VALIDACION)


# --- Dataset real -------------------------------------------------------------------------

def test_cantidad_minima(entrenamiento, validacion):
    assert len(entrenamiento) >= MINIMO_EJEMPLOS_ENTRENAMIENTO
    assert len(validacion) >= len(CATEGORIAS)


@pytest.mark.parametrize("ruta", [RUTA_ENTRENAMIENTO, RUTA_VALIDACION])
def test_salidas_json_con_claves_exactas_y_categorias_validas(ruta):
    for ejemplo in cargar_ejemplos(ruta):
        assert set(ejemplo) == {"entrada", "salida"}
        salida = json.loads(ejemplo["salida"])
        assert tuple(salida) == CLAVES_SALIDA
        assert salida["categoria"] in CATEGORIAS
        assert isinstance(salida["accion_sugerida"], str) and salida["accion_sugerida"].strip()


@pytest.mark.parametrize("ruta", [RUTA_ENTRENAMIENTO, RUTA_VALIDACION])
def test_dataset_real_sin_errores(ruta):
    assert errores(validar_dataset(cargar_ejemplos(ruta))) == []


def test_sin_duplicados_ni_fugas(entrenamiento, validacion):
    entradas = [e["entrada"] for e in entrenamiento + validacion]
    assert len(entradas) == len(set(entradas))
    assert errores(solapamiento(entrenamiento, validacion)) == []


def test_todas_las_categorias_cubiertas_y_balance(entrenamiento, validacion):
    for datos in (entrenamiento, validacion):
        resumen = chequear_balance(datos)
        assert resumen.categorias_ausentes == []
        assert resumen.relacion_max_min == 1.0


def test_casos_requeridos_presentes(entrenamiento, validacion):
    texto = " ".join(e["entrada"] for e in entrenamiento + validacion).lower()
    for marca in ("timeout", "connecterror", "api key not valid", "401", "403", "429",
                  "modulenotfounderror", "permission", "sqlite3", "dimension", "colección"):
        assert marca in texto, marca


def test_autenticacion_nunca_sugiere_reintentar(entrenamiento, validacion):
    """Coherencia con src/rag/reintentos.py: las credenciales nunca se reintentan."""
    for ejemplo in entrenamiento + validacion:
        salida = json.loads(ejemplo["salida"])
        if salida["categoria"] == "autenticacion":
            assert "no reintentar" in salida["accion_sugerida"]
            assert "backoff" not in salida["accion_sugerida"]


# --- Tipos reales del SDK -----------------------------------------------------------------

def test_conversion_a_tuning_example_real(entrenamiento):
    ejemplos = a_tuning_examples(entrenamiento)
    assert all(isinstance(e, types.TuningExample) for e in ejemplos)
    assert ejemplos[0].text_input == entrenamiento[0]["entrada"]
    assert json.loads(ejemplos[0].output) == json.loads(entrenamiento[0]["salida"])
    dataset = construir_tuning_dataset(entrenamiento)
    assert isinstance(dataset, types.TuningDataset) and len(dataset.examples) == len(entrenamiento)


def test_info_sdk_reporta_tipos():
    info = ct.info_sdk()
    assert info["instalado"]
    assert all(info["tipos"][n] for n in ("TuningExample", "TuningDataset", "TuningMode", "AdapterSize",
                                          "CreateTuningJobConfig"))
    assert "ADAPTER_SIZE_ONE" in info["adapter_sizes"]


def test_config_peft_local():
    config = ct.construir_config_peft()
    assert isinstance(config, types.CreateTuningJobConfig)
    assert config.tuning_mode == types.TuningMode.TUNING_MODE_PEFT_ADAPTER
    assert config.adapter_size == types.AdapterSize.ADAPTER_SIZE_ONE
    assert config.epoch_count is None  # No se inventan hiperparámetros.
    assert ct.construir_config_peft(epoch_count=3).epoch_count == 3
    with pytest.raises(ValueError):
        ct.construir_config_peft(epoch_count=0)
    with pytest.raises(KeyError):
        ct.construir_config_peft(adapter_size="ADAPTER_SIZE_INEXISTENTE")


def test_compatibilidad_sdk_inline_peft_rechazada_en_ambos_modos(entrenamiento):
    compat = ct.verificar_compatibilidad(construir_tuning_dataset(entrenamiento), ct.construir_config_peft())
    if not compat["verificable"]:
        pytest.skip(compat["motivo"])
    assert "adapter_size" in compat["gemini_developer_api"]
    assert "examples" in compat["vertex"]


def test_compatibilidad_sdk_gcs_peft_solo_vertex():
    compat = ct.verificar_compatibilidad(ct.dataset_gcs_pendiente(), ct.construir_config_peft())
    if not compat["verificable"]:
        pytest.skip(compat["motivo"])
    assert compat["vertex"] is None
    assert "gcs_uri" in compat["gemini_developer_api"]


# --- Seguridad: nada de entrenamiento ni de red ------------------------------------------

class ClienteEspia:
    def __init__(self):
        self.llamadas = 0
        self.tunings = self

    def tune(self, **kwargs):
        self.llamadas += 1
        raise AssertionError("No debe llamarse a tune en las pruebas")


def test_tuning_prohibido_por_defecto(monkeypatch):
    monkeypatch.delenv(ct.VARIABLE_AUTORIZACION, raising=False)
    cliente = ClienteEspia()
    with pytest.raises(ct.EntrenamientoNoAutorizadoError) as error:
        ct.crear_trabajo_tuning(cliente, base_model="cualquiera", training_dataset=None, config=None)
    assert "autorización" in str(error.value) and "no está verificado" in str(error.value)
    assert cliente.llamadas == 0


def test_tuning_bloqueado_aun_con_autorizacion_si_modelo_no_verificado(monkeypatch):
    monkeypatch.setenv(ct.VARIABLE_AUTORIZACION, ct.FRASE_AUTORIZACION)
    cliente = ClienteEspia()
    with pytest.raises(ct.EntrenamientoNoAutorizadoError, match="no está verificado"):
        ct.crear_trabajo_tuning(cliente, base_model="gemini-3.5-flash-lite", training_dataset=None, config=None,
                                autorizacion=ct.FRASE_AUTORIZACION)
    assert cliente.llamadas == 0
    assert ct.MODELOS_TUNING_VERIFICADOS == frozenset()


def test_tuning_solo_con_las_tres_condiciones(monkeypatch):
    """Con cliente falso: demuestra que las tres condiciones son necesarias y suficientes."""
    monkeypatch.setenv(ct.VARIABLE_AUTORIZACION, ct.FRASE_AUTORIZACION)
    monkeypatch.setattr(ct, "MODELOS_TUNING_VERIFICADOS", frozenset({"modelo-de-prueba"}))

    class ClienteFalso:
        def __init__(self):
            self.argumentos = None
            self.tunings = self

        def tune(self, **kwargs):
            self.argumentos = kwargs
            return "trabajo-simulado"

    cliente = ClienteFalso()
    assert ct.crear_trabajo_tuning(cliente, base_model="modelo-de-prueba", training_dataset="d", config="c",
                                   autorizacion=ct.FRASE_AUTORIZACION) == "trabajo-simulado"
    assert cliente.argumentos["base_model"] == "modelo-de-prueba"


def test_importar_y_ejecutar_cli_sin_red_ni_clientes():
    """Proceso aislado: sockets y genai.Client bloqueados; importar todo y correr el CLI debe funcionar."""
    codigo = textwrap.dedent("""
        import socket, sys
        def _bloqueado(*a, **k):
            raise RuntimeError("RED BLOQUEADA EN LA PRUEBA")
        socket.socket.connect = _bloqueado
        socket.create_connection = _bloqueado
        import google.genai as genai
        class _SinCliente:
            def __init__(self, *a, **k):
                raise RuntimeError("SE INTENTÓ CREAR genai.Client")
        genai.Client = _SinCliente
        import src.personalizacion.dataset, src.personalizacion.validacion, src.personalizacion.balance
        import src.personalizacion.configuracion_tuning, src.personalizacion.evaluacion
        import src.dataset_tuning
        from src.dataset_tuning import main
        sys.exit(main([]))
    """)
    proceso = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ_REPO, capture_output=True, text=True,
                             encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
                             timeout=120)
    assert proceso.returncode == 0, proceso.stderr[-2000:]
    assert "No se creó ningún trabajo de tuning" in proceso.stdout
    assert "RED BLOQUEADA" not in proceso.stderr and "genai.Client" not in proceso.stderr
