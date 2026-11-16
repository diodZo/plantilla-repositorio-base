"""Métricas de recuperación (Bloque 27): Precision@k, Recall@k, F1 y Hit@k.

Funciones puras, sin dependencias de Chroma ni de Gemini.

Convenciones:
- Los rankings se deduplican conservando el orden de la primera aparición: un ID repetido
  no cuenta como dos aciertos ni ocupa dos posiciones del denominador.
- Precision@k = |relevantes ∩ recuperados| / |recuperados únicos|; 0.0 si no hay recuperados.
  Si el sistema devuelve menos de k resultados, el denominador es lo devuelto (no k).
- Recall@k = |relevantes ∩ recuperados| / |relevantes|; None si no hay relevantes
  (consulta sin respuesta): no se cuenta como recall perfecto ni como cero.
- F1 = 2PR / (P + R); 0.0 si P = R = 0; None si P o R son None.
- Hit@k = 1.0 si hay al menos un relevante en el top-k, 0.0 si no; None sin relevantes.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def _validar_ids(ids, nombre: str) -> list[str]:
    if isinstance(ids, (str, bytes)) or not isinstance(ids, Iterable):
        raise TypeError(f"{nombre} debe ser una colección de IDs (lista, tupla o conjunto), no {type(ids).__name__}.")
    lista = list(ids)
    for i in lista:
        if not isinstance(i, str) or not i.strip():
            raise ValueError(f"{nombre} contiene un ID inválido: {i!r}. Los IDs deben ser cadenas no vacías.")
    return lista


def deduplicar(ids: Sequence[str]) -> list[str]:
    """Quita repetidos conservando el orden del ranking."""
    vistos: set[str] = set()
    return [i for i in _validar_ids(ids, "ids") if not (i in vistos or vistos.add(i))]


def top_k(ids_recuperados: Sequence[str], k: int) -> list[str]:
    """Los primeros k IDs únicos del ranking."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k debe ser un entero >= 1.")
    return deduplicar(ids_recuperados)[:k]


def precision_at_k(ids_recuperados: Sequence[str], ids_relevantes: Iterable[str]) -> float:
    """Proporción de recuperados (únicos) que son relevantes. Recibe el ranking ya cortado en k."""
    recuperados = deduplicar(ids_recuperados)
    relevantes = set(_validar_ids(ids_relevantes, "ids_relevantes"))
    if not recuperados:
        return 0.0
    return sum(i in relevantes for i in recuperados) / len(recuperados)


def recall_at_k(ids_recuperados: Sequence[str], ids_relevantes: Iterable[str]) -> float | None:
    """Proporción de relevantes que aparecen en lo recuperado; None si no hay relevantes."""
    recuperados = set(deduplicar(ids_recuperados))
    relevantes = set(_validar_ids(ids_relevantes, "ids_relevantes"))
    if not relevantes:
        return None
    return len(relevantes & recuperados) / len(relevantes)


def f1_score(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    for nombre, valor in (("precision", precision), ("recall", recall)):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0.0 <= valor <= 1.0:
            raise ValueError(f"{nombre} debe estar entre 0.0 y 1.0; se recibió {valor!r}.")
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def hit_at_k(ids_recuperados: Sequence[str], ids_relevantes: Iterable[str]) -> float | None:
    relevantes = set(_validar_ids(ids_relevantes, "ids_relevantes"))
    if not relevantes:
        return None
    return 1.0 if relevantes & set(deduplicar(ids_recuperados)) else 0.0


def metricas_en_k(ids_recuperados: Sequence[str], ids_relevantes: Iterable[str], k: int) -> dict:
    """Corta el ranking en k (sin duplicados) y calcula las cuatro métricas."""
    seleccion = top_k(ids_recuperados, k)
    relevantes = set(_validar_ids(ids_relevantes, "ids_relevantes"))
    p = precision_at_k(seleccion, relevantes)
    r = recall_at_k(seleccion, relevantes)
    return {
        "k": k,
        "recuperados": seleccion,
        "aciertos": [i for i in seleccion if i in relevantes],
        "precision": p,
        "recall": r,
        "f1": f1_score(p, r) if r is not None else None,
        "hit": hit_at_k(seleccion, relevantes),
    }


def promedio(valores: Iterable[float | None]) -> dict:
    """Media ignorando None. Devuelve {'media', 'n', 'excluidos'} (media None si n = 0)."""
    lista = list(valores)
    validos = [v for v in lista if v is not None]
    return {
        "media": (sum(validos) / len(validos)) if validos else None,
        "n": len(validos),
        "excluidos": len(lista) - len(validos),
    }
