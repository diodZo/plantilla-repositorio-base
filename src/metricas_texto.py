"""Bloque 16: métricas de coincidencia léxica basadas en Counter.

No confundir un F1 alto con precisión factual o similitud semántica.
"""
from collections import Counter
from src.pipeline_texto import procesar_texto


def contar_coincidencias(tokens_referencia: list[str], tokens_respuesta: list[str]) -> int:
    """Suma mínimos de frecuencia para cada palabra compartida."""
    return sum((Counter(tokens_referencia) & Counter(tokens_respuesta)).values())


def calcular_precision_cobertura_f1(
    tokens_referencia: list[str], tokens_respuesta: list[str]
) -> dict[str, float]:
    """Devuelve 0 en los tres indicadores si algún lado está vacío."""
    if not tokens_referencia or not tokens_respuesta:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}
    comunes = contar_coincidencias(tokens_referencia, tokens_respuesta)
    precision = comunes / len(tokens_respuesta)
    cobertura = comunes / len(tokens_referencia)
    f1 = 2 * precision * cobertura / (precision + cobertura) if precision + cobertura else 0.0
    return {"precision": precision, "cobertura": cobertura, "f1": f1}


def calcular_metricas(texto_referencia: str, texto_respuesta: str) -> dict[str, float]:
    """Normaliza ambos textos y calcula precisión, cobertura y F1."""
    return calcular_precision_cobertura_f1(
        procesar_texto(texto_referencia), procesar_texto(texto_respuesta)
    )


def resumir_metricas(resultados: list[dict]) -> dict[str, float]:
    if not resultados:
        return {"precision_promedio": 0.0, "cobertura_promedio": 0.0, "f1_promedio": 0.0}
    n = len(resultados)
    return {f"{nombre}_promedio": sum(r[nombre] for r in resultados) / n
            for nombre in ("precision", "cobertura", "f1")}


if __name__ == "__main__":
    referencia = "El gato duerme en el sofá."
    respuesta = "El gato duerme en el sillón todo el día."
    print(calcular_metricas(referencia, respuesta))
