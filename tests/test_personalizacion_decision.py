"""Bloque 30: puntuación de estrategias, empates, evidencia y generación del documento. Todo offline."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import date

import pytest

from src.personalizacion import decision as d
from src.personalizacion.dataset import RAIZ_REPO
from src.personalizacion.documento_decision import SECCIONES, generar_documento
from src.personalizacion.salida_estructurada import (
    SalidaClasificacion, construir_config_generacion, construir_prompt, es_valida, parsear_respuesta,
)


def valores(**cambios):
    base = {c: False for c in d.CRITERIOS}
    base.update(cambios)
    return base


# --- Puntuación y empates ---------------------------------------------------------------------

PESOS_OFICIALES = {  # (RAG, Fine-tuning completo, PEFT) según el PDF del Bloque 30
    "informacion_cambia_seguido": (3, 0, 0),
    "problema_de_formato_o_tono": (0, 1, 2),
    "dataset_grande_y_de_calidad": (0, 2, 1),
    "presupuesto_limitado_o_iterar_rapido": (2, 0, 1),
    "necesita_multiples_variantes": (0, 0, 2),
}


def test_pesos_son_los_oficiales():
    assert {c: tuple(d.PESOS[c][e] for e in d.ESTRATEGIAS) for c in d.CRITERIOS} == PESOS_OFICIALES


def test_escenario_a_hipotesis_inicial():
    resultado = d.puntuar(d.HIPOTESIS_INICIAL)
    assert resultado.puntos == {"RAG": 2, "Fine-tuning completo": 1, "PEFT": 3}
    assert resultado.empatadas == ["PEFT"] and resultado.ganadora == "PEFT" and not resultado.hay_empate
    assert not resultado.provisional


def test_escenario_b_ejemplo_oficial_del_curso():
    resultado = d.puntuar(d.EJEMPLO_OFICIAL_CURSO)
    assert resultado.puntos == {"RAG": 0, "Fine-tuning completo": 3, "PEFT": 3}
    assert resultado.empatadas == ["Fine-tuning completo", "PEFT"]
    assert resultado.hay_empate and resultado.ganadora is None


@pytest.mark.parametrize("criterio", list(PESOS_OFICIALES))
def test_sensibilidad_cada_criterio_aislado_suma_su_fila(criterio):
    """Desde todo «No», activar un solo criterio da exactamente su fila de pesos."""
    puntos = d.puntuar(valores(**{criterio: True})).puntos
    assert tuple(puntos[e] for e in d.ESTRATEGIAS) == PESOS_OFICIALES[criterio]


@pytest.mark.parametrize("criterio", list(PESOS_OFICIALES))
def test_sensibilidad_invertir_cada_criterio_de_la_hipotesis(criterio):
    """Invertir un criterio de la hipótesis suma o resta exactamente su fila de pesos."""
    base = d.puntuar(d.HIPOTESIS_INICIAL).puntos
    original = d.HIPOTESIS_INICIAL[criterio]
    cambiado = d.puntuar({**d.HIPOTESIS_INICIAL, criterio: not original}).puntos
    signo = -1 if original else 1
    for e, peso in zip(d.ESTRATEGIAS, PESOS_OFICIALES[criterio]):
        assert cambiado[e] == base[e] + signo * peso


def test_sensibilidad_primer_lugar_al_invertir_cada_criterio_de_la_hipotesis():
    filas = {(n, alt): r.empatadas for n, _, alt, r in d.sensibilidad(d.HIPOTESIS_INICIAL)}
    assert filas == {
        ("informacion_cambia_seguido", True): ["RAG"],                       # RAG 5, FT 1, PEFT 3
        ("problema_de_formato_o_tono", False): ["RAG"],                      # RAG 2, FT 0, PEFT 1
        ("dataset_grande_y_de_calidad", True): ["PEFT"],                     # RAG 2, FT 3, PEFT 4
        ("presupuesto_limitado_o_iterar_rapido", False): ["PEFT"],           # RAG 0, FT 1, PEFT 2
        ("necesita_multiples_variantes", True): ["PEFT"],                    # RAG 2, FT 1, PEFT 5
    }


def test_sensibilidad_con_none_prueba_ambos_valores():
    filas = d.sensibilidad(valores(problema_de_formato_o_tono=None))
    probados = [(n, alt) for n, orig, alt, _ in filas if orig is None]
    assert probados == [("problema_de_formato_o_tono", True), ("problema_de_formato_o_tono", False)]


def test_todos_los_criterios_verdaderos():
    assert d.puntuar({c: True for c in d.CRITERIOS}).puntos == {"RAG": 5, "Fine-tuning completo": 3, "PEFT": 6}


def test_empate_devuelve_todas_las_empatadas_y_sin_ganadora():
    # RAG 3 (información), FT 1 + 2 y PEFT 2 + 1 (formato + dataset): empate de tres vías.
    resultado = d.puntuar(valores(informacion_cambia_seguido=True, problema_de_formato_o_tono=True,
                                  dataset_grande_y_de_calidad=True))
    assert resultado.puntos == {"RAG": 3, "Fine-tuning completo": 3, "PEFT": 3}
    assert resultado.empatadas == ["RAG", "Fine-tuning completo", "PEFT"]
    assert resultado.hay_empate and resultado.ganadora is None


def test_empate_total_en_cero():
    resultado = d.puntuar(valores())
    assert resultado.empatadas == list(d.ESTRATEGIAS) and resultado.ganadora is None


def test_empate_no_depende_del_orden_del_diccionario():
    a = dict(d.EJEMPLO_OFICIAL_CURSO)
    b = dict(reversed(list(a.items())))
    assert d.puntuar(a).empatadas == d.puntuar(b).empatadas == ["Fine-tuning completo", "PEFT"]


def test_no_verificado_no_suma_no_es_false_y_es_provisional():
    con_none = d.puntuar(valores(problema_de_formato_o_tono=None, presupuesto_limitado_o_iterar_rapido=True))
    con_false = d.puntuar(valores(presupuesto_limitado_o_iterar_rapido=True))
    assert con_none.puntos == con_false.puntos == {"RAG": 2, "Fine-tuning completo": 0, "PEFT": 1}
    assert con_none.no_verificados == ["problema_de_formato_o_tono"] and con_none.provisional
    assert con_false.no_verificados == [] and not con_false.provisional
    assert con_none.maximo_posible == {"RAG": 2, "Fine-tuning completo": 1, "PEFT": 3}
    assert con_false.maximo_posible == con_false.puntos


def test_valores_comprobados_del_repositorio_son_provisionales():
    """Valores que hoy da la evidencia: información Sí (parcial), formato None, dataset No, presupuesto Sí, variantes No."""
    comprobados = valores(informacion_cambia_seguido=True, problema_de_formato_o_tono=None,
                          presupuesto_limitado_o_iterar_rapido=True)
    resultado = d.puntuar(comprobados)
    assert resultado.puntos == {"RAG": 5, "Fine-tuning completo": 0, "PEFT": 1}
    assert resultado.ganadora == "RAG" and resultado.provisional
    escenarios = d.escenarios_no_verificados(comprobados)
    assert [(a, r.puntos) for a, r in escenarios] == [
        ({"problema_de_formato_o_tono": True}, {"RAG": 5, "Fine-tuning completo": 1, "PEFT": 3}),
        ({"problema_de_formato_o_tono": False}, {"RAG": 5, "Fine-tuning completo": 0, "PEFT": 1}),
    ]
    # Si los dos criterios de comprobación parcial resultaran «No» y el formato «Sí», el primer lugar cambia.
    assert d.puntuar({**comprobados, "informacion_cambia_seguido": False,
                      "presupuesto_limitado_o_iterar_rapido": False,
                      "problema_de_formato_o_tono": True}).empatadas == ["PEFT"]


@pytest.mark.parametrize("entrada, error", [
    ({"informacion_cambia_seguido": True}, ValueError),
    ({**{c: False for c in d.CRITERIOS}, "otro": True}, ValueError),
    ({**{c: False for c in d.CRITERIOS}, "informacion_cambia_seguido": "si"}, TypeError),
])
def test_puntuar_valida_criterios(entrada, error):
    with pytest.raises(error):
        d.puntuar(entrada)


# --- Evidencia ----------------------------------------------------------------------------------

def test_evidencia_informacion_con_fechas_simuladas():
    ref = date(2026, 11, 16)
    e = d.evidencia_informacion([date(2026, 11, 1), date(2026, 9, 1)], date(2026, 8, 1), ref)
    assert e.valor is True and e.estado == d.VERIFICADO and "en 1 commit " in e.detalle
    e = d.evidencia_informacion([date(2026, 9, 1)], date(2026, 8, 1), ref)
    assert e.valor is False
    e = d.evidencia_informacion([date(2026, 11, 10)], date(2026, 10, 8), ref)
    assert e.valor is True and e.estado == d.PARCIAL
    assert d.evidencia_informacion([], date(2026, 11, 1), ref).valor is None  # historial < 30 días
    assert d.evidencia_informacion(None, None, None).estado == d.NO_VERIFICADO


def test_evidencia_formato_sin_muestra_no_inventa(tmp_path):
    e = d.evidencia_formato(tmp_path / "no_existe.json")
    assert e.valor is None and e.estado == d.NO_VERIFICADO and "%" not in e.detalle.replace("porcentaje", "")


def test_evidencia_formato_con_muestra(tmp_path):
    bien = '{"categoria": "red", "accion_sugerida": "reintentar con backoff"}'
    ruta = tmp_path / "respuestas.json"
    ruta.write_text(json.dumps({"origen": "simulado", "respuestas": [bien] * 17 + ["no json"] * 3}), encoding="utf-8")
    e = d.evidencia_formato(ruta)
    assert e.valor is True and "15%" in e.detalle  # 3/20 = 15 % alcanza el umbral
    ruta.write_text(json.dumps({"respuestas": [bien] * 18 + ["no json"] * 2}), encoding="utf-8")
    assert d.evidencia_formato(ruta).valor is False
    ruta.write_text(json.dumps([bien] * 5), encoding="utf-8")
    assert d.evidencia_formato(ruta).valor is None  # muestra < 20


def test_evidencia_dataset():
    assert d.evidencia_dataset(35).valor is False
    assert d.evidencia_dataset(250).valor is None
    assert d.evidencia_dataset(250, True).valor is True


def test_evidencia_presupuesto_en_repo_temporal(tmp_path):
    assert d.evidencia_presupuesto(tmp_path).valor is None
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "indexar_corpus.py").write_text("# para respetar la cuota por minuto", encoding="utf-8")
    e = d.evidencia_presupuesto(tmp_path)
    assert e.valor is True and e.estado == d.PARCIAL


def test_recomendacion_con_empate_es_linea_base():
    rec = d.recomendar(d.puntuar(d.EJEMPLO_OFICIAL_CURSO))
    assert rec["inmediata"].startswith("Prompt + Pydantic") and "PEFT" in rec["futura"]
    assert "empate entre Fine-tuning completo y PEFT" in rec["motivo"]


def test_recomendacion_con_rag_provisional():
    resultado = d.puntuar(valores(informacion_cambia_seguido=True, presupuesto_limitado_o_iterar_rapido=True,
                                  problema_de_formato_o_tono=None))
    rec = d.recomendar(resultado)
    assert rec["inmediata"].startswith("Prompt + Pydantic") and "catálogo" in rec["inmediata"]
    assert "provisional" in rec["motivo"] and "sin medirse" in rec["motivo"]


# --- Documento Markdown ------------------------------------------------------------------------

def _documento(evidencias=None, resultado=None):
    evidencias = evidencias or d.recopilar_evidencia(
        35, RAIZ_REPO, RAIZ_REPO / "no_existe.json",
        fechas=([date(2026, 11, 12)], date(2026, 10, 8), date(2026, 11, 16)))
    conteos = {c: 5 for c in ("red", "autenticacion", "cuota", "entorno", "consistencia_indice")}
    compat = {"ejemplos inline": {"verificable": True, "gemini_developer_api": "x", "vertex": "y"},
              "dataset en Cloud Storage": {"verificable": True, "gemini_developer_api": "z", "vertex": None}}
    return generar_documento(
        conteos_entrenamiento=conteos, conteos_validacion={c: 2 for c in conteos}, evidencias=evidencias,
        resultado=resultado or d.puntuar(d.valores_de(evidencias)), resultado_hipotesis=d.puntuar(d.HIPOTESIS_INICIAL),
        sdk={"version": "9.9.9"}, compatibilidad=compat, referencia_git="HEAD de prueba")


def test_documento_tiene_exactamente_cuatro_secciones():
    texto = _documento()
    assert re.findall(r"^## .*$", texto, flags=re.MULTILINE) == list(SECCIONES)


def test_documento_muestra_puntos_empate_y_criterios():
    texto = _documento()
    assert "**Primer lugar sin empate:** RAG (5 puntos)" in texto
    assert "Puntaje PROVISIONAL" in texto and "no se trata como «No»" in texto
    assert "| `informacion_cambia_seguido` | 3 | 0 | 0 |" in texto
    assert "El primer lugar **no depende** de los criterios no verificados" in texto
    assert "Sensibilidad" in texto
    assert "RAG 0, Fine-tuning completo 3, PEFT 3. **Empate en el primer lugar:** Fine-tuning completo, PEFT" in texto
    for criterio in d.CRITERIOS:
        assert f"`{criterio}`" in texto
    assert "No verificado" in texto and "Supuesto" in texto
    assert "165 más" in texto and "35 (25 entrenamiento + 10 validación)" in texto
    assert "mínimo orientativo del curso, no de la API" in texto
    assert "solo acepta PEFT" in texto and "9.9.9" in texto


def test_documento_no_afirma_entrenamiento_ni_superioridad():
    texto = _documento().lower()
    assert "no se llamó a la api" in texto
    for frase in ("modelo entrenado", "se entrenó", "peft superó", "peft supera", "es superior"):
        assert frase not in texto


def test_cli_decision_escribe_en_tmp(tmp_path, capsys):
    from src.decision_personalizacion import main

    salida = tmp_path / "decision.md"
    assert main(["--salida", str(salida), "--respuestas-base", str(tmp_path / "no_existe.json")]) == 0
    texto = salida.read_text(encoding="utf-8")
    assert re.findall(r"^## .*$", texto, flags=re.MULTILINE) == list(SECCIONES)
    assert "Empatadas en primer lugar" in capsys.readouterr().out or "Primer lugar" in texto


# --- Línea base Prompt + Pydantic (local) -----------------------------------------------------

def test_esquema_pydantic_estricto():
    assert parsear_respuesta('{"categoria": "cuota", "accion_sugerida": "esperar"}').categoria == "cuota"
    for malo in ('{"categoria": "disco", "accion_sugerida": "x"}', '{"categoria": "red"}',
                 '{"categoria": "red", "accion_sugerida": "x", "extra": 1}', '{"categoria": "red", "accion_sugerida": "  "}',
                 "no es json"):
        assert not es_valida(malo), malo
    assert set(SalidaClasificacion.model_fields) == {"categoria", "accion_sugerida"}


def test_config_generacion_y_prompt_locales():
    types = pytest.importorskip("google.genai.types")
    config = construir_config_generacion()
    assert isinstance(config, types.GenerateContentConfig)
    assert config.response_mime_type == "application/json" and config.response_schema is SalidaClasificacion
    prompt = construir_prompt("Error 429", [{"entrada": "Timeout", "salida": "{}"}])
    assert prompt.endswith("Error: Error 429\nJSON:") and "Error: Timeout" in prompt


def test_modulos_bloque30_se_importan_sin_red_ni_clientes():
    codigo = textwrap.dedent("""
        import socket
        def _bloqueado(*a, **k):
            raise RuntimeError("RED BLOQUEADA EN LA PRUEBA")
        socket.socket.connect = _bloqueado
        socket.create_connection = _bloqueado
        import google.genai as genai
        class _SinCliente:
            def __init__(self, *a, **k):
                raise RuntimeError("SE INTENTÓ CREAR genai.Client")
        genai.Client = _SinCliente
        import src.personalizacion.decision, src.personalizacion.documento_decision
        import src.personalizacion.salida_estructurada, src.decision_personalizacion
        from src.decision_personalizacion import main
        main(["--no-escribir"])
    """)
    proceso = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ_REPO, capture_output=True, text=True,
                             encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert proceso.returncode == 0, proceso.stderr[-2000:]
    assert "Recomendación" in proceso.stdout
