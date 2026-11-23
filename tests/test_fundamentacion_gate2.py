"""Gate 2: citación y fundamentación en tres niveles (estructural, relevancia, respaldo). Sin red.

Las señales de relevancia y respaldo son HEURÍSTICAS LÉXICAS: estas pruebas fijan tanto lo que
detectan como lo que NO detectan (falsos negativos y positivos conocidos). No hay verificación semántica.
"""
from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage

from src.rag.fundamentacion import decidir, evaluar_fundamentacion, oraciones_citadas
from src.servicio_rag import (
    CORPUS_DEMO, RESPUESTA_CITAS_INVALIDAS, RESPUESTA_FUENTE_NO_PERTINENTE, cerrar_servicio, crear_servicio_demo,
)

POLITICA = ("[Política de devoluciones > Plazo de devolución]\nLos clientes pueden devolver un producto dentro de "
            "los 30 días siguientes a la compra, presentando la boleta y el producto sin uso.")
GARANTIA = "[Garantía > Cobertura]\nLa garantía legal cubre fallas de fabricación durante 6 meses. No cubre daños por mal uso."
PREGUNTA = "¿En qué plazo puedo devolver un producto?"


def senales(respuesta, pregunta=PREGUNTA, textos=None):
    return evaluar_fundamentacion(pregunta, respuesta, textos or {1: POLITICA, 2: GARANTIA})


# --- Unidad: oraciones y señales ---------------------------------------------------------------

def test_oraciones_con_cita_tras_el_punto():
    assert oraciones_citadas("Primera afirmación. [1] Segunda [2][3]. Sin cita.") == [
        ("Primera afirmación.", [1]), ("Segunda.", [2, 3]), ("Sin cita.", [])]


def test_respuesta_respaldada_pasa_las_heuristicas():
    s = senales("Puedes devolver un producto dentro de los 30 días siguientes a la compra [1].")
    assert s["cobertura_minima"] == 1.0 and s["terminos_comunes_pregunta_fuente"] >= 2
    assert decidir(s) is None
    assert s["metodo"] == "heuristica_lexica" and s["verificacion_semantica"] == "no_realizada"


def test_numero_contradictorio_se_rechaza():
    assert decidir(senales("Puedes devolver un producto dentro de 45 días [1]."))[0] == "rechazada_posible_contradiccion"


def test_negacion_contradictoria_se_rechaza():
    estado, motivo = decidir(senales("No se pueden devolver productos [1]."))
    assert estado == "rechazada_posible_contradiccion" and "negación" in motivo


def test_negacion_presente_en_la_fuente_no_se_marca():
    assert decidir(senales("La garantía no cubre daños por mal uso [2].", "¿Qué no cubre la garantía?")) is None


def test_vocabulario_ajeno_a_la_fuente_se_rechaza():
    s = senales("Los reembolsos se acreditan con el mismo medio de pago usado [1].")
    assert decidir(s)[0] == "rechazada_respaldo_insuficiente" and s["cobertura_minima"] < 0.5


def test_fuente_sin_relacion_con_la_pregunta_se_abstiene():
    s = senales("La garantía legal cubre fallas de fabricación durante 6 meses [2].", "¿Cómo se reembolsa una devolución?")
    assert s["terminos_comunes_pregunta_fuente"] == 0 and decidir(s) == ("abstencion", "fuente_no_pertinente")


def test_falso_negativo_conocido_parafrasis_falsa_con_las_mismas_palabras():
    """LIMITACIÓN: misma palabras y números, significado distinto → la heurística NO lo detecta."""
    s = senales("La compra debe presentarse 30 días antes de devolver el producto [1].")
    assert decidir(s) is None


def test_falso_positivo_conocido_sinonimos():
    """LIMITACIÓN: una respuesta correcta con sinónimos se rechaza (política conservadora)."""
    s = senales("Tienes un mes para retornar el artículo adquirido [1].")
    assert decidir(s)[0] == "rechazada_respaldo_insuficiente"


# --- Servicio integrado ------------------------------------------------------------------------

class ModeloFijo:
    def __init__(self, texto):
        self.texto, self.llamadas = texto, 0

    def invoke(self, mensajes, config=None):
        self.llamadas += 1
        return AIMessage(content=self.texto, usage_metadata=None)


@pytest.fixture
def servicio_con(tmp_path):
    nombres = []

    def _crear(texto, documentos=None):
        nombre = f"gate2.fund.{uuid.uuid4().hex}"
        nombres.append(nombre)
        return crear_servicio_demo(tmp_path / nombre, documentos, nombre, ModeloFijo(texto))[0]
    yield _crear
    for nombre in nombres:
        cerrar_servicio(nombre)


def test_cita_inexistente(servicio_con):
    r = servicio_con("El plazo es de 30 días [9].").consultar(PREGUNTA)
    assert (r.estado, r.fuentes, r.respuesta) == ("rechazada_citas_invalidas", [], RESPUESTA_CITAS_INVALIDAS)


def test_cita_a_fuente_descartada_por_numero(servicio_con):
    """Corpus política + FAQ malicioso: queda solo [1]; citar [2] (la posición que tendría el FAQ) es inválido."""
    servicio = servicio_con("Los reembolsos se procesan con el mismo medio de pago [2].", CORPUS_DEMO[:2])
    r = servicio.consultar("¿Cómo se procesan los reembolsos de una devolución?")
    assert r.unidades_descartadas == 1 and r.fuentes_contexto == [{"numero": 1, "documento": "demo/politica_devoluciones.md"}]
    assert r.estado == "rechazada_citas_invalidas" and r.fuentes == []


def test_contenido_de_fuente_descartada_atribuido_a_otra(servicio_con):
    """Atribuir a [1] (política) el contenido del FAQ descartado: la cita es válida, el respaldo no."""
    servicio = servicio_con("Los reembolsos se procesan con el mismo medio de pago usado en la compra [1].", CORPUS_DEMO[:2])
    r = servicio.consultar("¿Cómo se procesan los reembolsos de una devolución?")
    assert r.estado in ("rechazada_respaldo_insuficiente", "abstencion") and r.fuentes == []


def test_pregunta_sin_informacion_suficiente(servicio_con):
    r = servicio_con("Según la documentación, los clientes pueden devolver un producto [1].").consultar(
        "¿Cuál es el horario de atención de la tienda?")
    assert (r.estado, r.motivo, r.respuesta) == ("abstencion", "fuente_no_pertinente", RESPUESTA_FUENTE_NO_PERTINENTE)


def test_contradiccion_evidente_con_el_contexto(servicio_con):
    r = servicio_con("Los clientes pueden devolver un producto dentro de los 90 días siguientes a la compra [1].").consultar(PREGUNTA)
    assert r.estado == "rechazada_posible_contradiccion" and r.fuentes == []
    assert r.fundamentacion["numeros_no_respaldados"] == 1


def test_caso_observado_reembolsos_ahora_se_abstiene(tmp_path):
    """Regresión del ensayo anterior: con el modelo simulado, la cita a garantía era válida pero irrelevante."""
    servicio, _ = crear_servicio_demo(tmp_path, nombre_logger="gate2.fund.caso")
    try:
        r = servicio.consultar("¿Cómo se reembolsa una devolución?")
        assert (r.estado, r.motivo, r.fuentes) == ("abstencion", "fuente_no_pertinente", [])
        assert r.fundamentacion["terminos_comunes_pregunta_fuente"] == 0
    finally:
        del servicio
        cerrar_servicio("gate2.fund.caso")


def test_senales_se_auditan_sin_texto(tmp_path):
    servicio, _ = crear_servicio_demo(tmp_path, nombre_logger="gate2.fund.log")
    try:
        servicio.consultar(PREGUNTA)
        texto = (tmp_path / "logs" / "rag_auditoria.jsonl").read_text(encoding="utf-8")
        assert '"fundamentacion": {"metodo": "heuristica_lexica", "verificacion_semantica": "no_realizada"' in texto
        assert "presentando la boleta" not in texto
    finally:
        del servicio
        cerrar_servicio("gate2.fund.log")
