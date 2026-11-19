"""Balance de categorías del dataset (Bloque 29), con `collections.Counter`.

Que `validar_dataset` no devuelva errores NO significa que el dataset esté balanceado: son
comprobaciones distintas. Este módulo solo describe la distribución; el umbral de relación
máximo/mínimo es una convención didáctica, no un requisito de la API.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from src.personalizacion.dataset import CATEGORIAS, categoria_de

UMBRAL_RELACION_DIDACTICO = 1.5


@dataclass
class ResumenBalance:
    total: int
    conteos: dict[str, int]
    porcentajes: dict[str, float]
    mayoritarias: list[str]
    minoritarias: list[str]
    relacion_max_min: float | None  # None si alguna categoría esperada tiene 0 ejemplos.
    sin_categoria_valida: int = 0
    categorias_ausentes: list[str] = field(default_factory=list)

    def dentro_de_umbral(self, umbral: float = UMBRAL_RELACION_DIDACTICO) -> bool:
        return self.relacion_max_min is not None and self.relacion_max_min <= umbral


def chequear_balance(ejemplos: list[dict], categorias: Iterable[str] = CATEGORIAS) -> ResumenBalance:
    """Cuenta ejemplos por categoría. Las categorías esperadas sin ejemplos aparecen con 0."""
    categorias = tuple(categorias)
    contador = Counter(categoria_de(e) if isinstance(e, dict) else None for e in ejemplos)
    sin_categoria = sum(n for c, n in contador.items() if c not in categorias)
    conteos = {c: contador.get(c, 0) for c in categorias}
    total = len(ejemplos)
    porcentajes = {c: (100 * n / total if total else 0.0) for c, n in conteos.items()}
    maximo = max(conteos.values(), default=0)
    minimo = min(conteos.values(), default=0)
    return ResumenBalance(
        total=total,
        conteos=conteos,
        porcentajes=porcentajes,
        mayoritarias=[c for c, n in conteos.items() if n == maximo],
        minoritarias=[c for c, n in conteos.items() if n == minimo],
        relacion_max_min=(maximo / minimo) if minimo else None,
        sin_categoria_valida=sin_categoria,
        categorias_ausentes=[c for c, n in conteos.items() if n == 0],
    )


def formatear_balance(resumen: ResumenBalance, umbral: float = UMBRAL_RELACION_DIDACTICO) -> str:
    lineas = [f"Total de ejemplos: {resumen.total}"]
    for categoria, n in resumen.conteos.items():
        lineas.append(f"  {categoria:<22} {n:>3}  ({resumen.porcentajes[categoria]:5.1f} %)")
    if resumen.sin_categoria_valida:
        lineas.append(f"  {'(sin categoría válida)':<22} {resumen.sin_categoria_valida:>3}")
    lineas.append(f"Mayoritaria(s): {', '.join(resumen.mayoritarias)}")
    lineas.append(f"Minoritaria(s): {', '.join(resumen.minoritarias)}")
    if resumen.relacion_max_min is None:
        lineas.append(f"Relación máx/mín: no calculable (categorías sin ejemplos: {resumen.categorias_ausentes})")
    else:
        estado = "dentro" if resumen.dentro_de_umbral(umbral) else "FUERA"
        lineas.append(f"Relación máx/mín: {resumen.relacion_max_min:.2f} ({estado} del umbral didáctico {umbral})")
    return "\n".join(lineas)
