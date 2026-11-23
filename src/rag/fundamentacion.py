"""Señales de fundamentación de una respuesta RAG (Gate 2). Tres niveles que NO son equivalentes:

1. Estructural (exacta): cada cita [n] existe en el contexto entregado al modelo
   (`generador.calcular_metricas`, Bloque 26). No dice nada sobre el contenido.
2. Relevancia de la fuente (heurística léxica): la fuente citada comparte al menos una raíz con
   la pregunta (`lexico.tokenizar`: minúsculas, sin tildes, sin stopwords, raíz de 5 letras).
3. Respaldo (heurística léxica): en cada oración citada, la mayoría de sus términos, todos sus
   números y sus negaciones aparecen en las fuentes que cita.

NO hay verificación semántica (NLI, juez LLM o revisión humana). Estas señales detectan casos
evidentes: una fuente sin relación con la pregunta, un número que no está en la fuente, una negación
ausente en la fuente o una oración con vocabulario ajeno. No detectan una paráfrasis falsa con las
mismas palabras, una negación de alcance distinto ni un razonamiento incorrecto. Y pueden rechazar
respuestas correctas que usan sinónimos. La política del servicio es conservadora: ante una señal
negativa se abstiene o rechaza la respuesta, en lugar de presentarla como fundamentada.
"""
from __future__ import annotations

import re

from src.rag.lexico import normalizar, tokenizar

UMBRAL_COBERTURA = 0.5
# Vocabulario de enlace de una respuesta ("según la documentación…"), que no afirma nada sobre el contenido.
META = frozenset({"segun", "docum", "conte", "fragm", "fuent", "indic", "simul", "infor", "propo"})
NEGACIONES = frozenset({"no", "nunca", "jamas", "ningun", "ninguna", "ninguno", "tampoco", "not", "never"})
_CITA = re.compile(r"\[(\d+)\]")
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def oraciones_citadas(respuesta: str) -> list[tuple[str, list[int]]]:
    """Divide en oraciones y asocia a cada una sus citas, incluidas las escritas tras el punto ("… uso. [1]")."""
    reordenado = re.sub(r"([.!?])\s*((?:\[\d+\]\s*)+)", lambda m: " " + m.group(2).strip() + m.group(1) + " ", respuesta)
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+|\n+", reordenado) if o.strip()]
    limpiar = lambda o: re.sub(r"\s+([.!?])", r"\1", re.sub(r"\s+", " ", _CITA.sub(" ", o))).strip()  # noqa: E731
    return [(limpiar(o), [int(n) for n in _CITA.findall(o)]) for o in oraciones]


def _numeros(texto: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMERO.findall(texto)}


def _tiene_negacion(texto: str) -> bool:
    return bool(set(re.findall(r"[a-z]+", normalizar(texto))) & NEGACIONES)


def evaluar_fundamentacion(pregunta: str, respuesta: str, textos_citas: dict[int, str]) -> dict:
    """Señales numéricas (sin texto) para decidir y auditar. `textos_citas`: {número: texto de la unidad}."""
    oraciones = oraciones_citadas(respuesta)
    citadas = [(o, [n for n in nums if n in textos_citas]) for o, nums in oraciones if nums]
    citadas = [(o, nums) for o, nums in citadas if nums]
    numeros_usados = sorted({n for _, nums in citadas for n in nums})
    texto_fuentes = " ".join(textos_citas[n] for n in numeros_usados)
    comunes = set(tokenizar(pregunta)) & set(tokenizar(texto_fuentes))

    coberturas, numeros_sin_respaldo, negaciones_sin_respaldo = [], set(), 0
    for oracion, nums in citadas:
        fuente = " ".join(textos_citas[n] for n in nums)
        terminos = [t for t in tokenizar(oracion) if t not in META and not t.isdigit()]
        if terminos:
            vocabulario = set(tokenizar(fuente))
            coberturas.append(sum(t in vocabulario for t in terminos) / len(terminos))
        numeros_sin_respaldo |= _numeros(oracion) - _numeros(fuente)
        negaciones_sin_respaldo += _tiene_negacion(oracion) and not _tiene_negacion(fuente)
    return {
        "metodo": "heuristica_lexica",
        "verificacion_semantica": "no_realizada",
        "oraciones_citadas": len(citadas),
        "oraciones_sin_cita": sum(1 for _, nums in oraciones if not nums),
        "terminos_comunes_pregunta_fuente": len(comunes),
        "cobertura_minima": round(min(coberturas), 3) if coberturas else None,
        "numeros_no_respaldados": len(numeros_sin_respaldo),
        "negaciones_no_respaldadas": negaciones_sin_respaldo,
    }


def decidir(senales: dict, umbral: float = UMBRAL_COBERTURA) -> tuple[str, str] | None:
    """(estado, motivo) si una señal obliga a no presentar la respuesta; None si pasan todas.

    Pasar todas NO significa respaldo semántico verificado.
    """
    if senales["oraciones_citadas"] and senales["terminos_comunes_pregunta_fuente"] == 0:
        return "abstencion", "fuente_no_pertinente"
    if senales["numeros_no_respaldados"]:
        return "rechazada_posible_contradiccion", "números ausentes en la fuente citada"
    if senales["negaciones_no_respaldadas"]:
        return "rechazada_posible_contradiccion", "negación ausente en la fuente citada"
    if senales["cobertura_minima"] is not None and senales["cobertura_minima"] < umbral:
        return "rechazada_respaldo_insuficiente", f"cobertura léxica {senales['cobertura_minima']} < {umbral}"
    return None
