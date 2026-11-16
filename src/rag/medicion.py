"""Medición de latencia por etapas con `time.perf_counter()` (Bloque 28).

- Cada etapa se mide con un context manager. El tiempo se registra aunque la etapa
  lance una excepción (se marca como fallida) y la excepción se propaga sin cambios.
- El total se mide de forma independiente (no es la suma de etapas). La diferencia,
  `sobrecarga_ms`, recoge validaciones, conversiones y cualquier trabajo fuera de las etapas.
- El reloj es inyectable para probar sin depender del tiempo real.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable


class Medidor:
    def __init__(self, reloj: Callable[[], float] = time.perf_counter):
        self._reloj = reloj
        self.tiempos_ms: dict[str, float] = {}
        self.etapas_fallidas: list[str] = []
        self.total_ms: float | None = None
        self._en_total = False

    @contextmanager
    def etapa(self, nombre: str):
        if not isinstance(nombre, str) or not nombre:
            raise ValueError("La etapa necesita un nombre.")
        if nombre in self.tiempos_ms:
            raise ValueError(f"La etapa {nombre!r} ya fue medida.")
        inicio = self._reloj()
        try:
            yield
        except BaseException:
            self.etapas_fallidas.append(nombre)
            raise
        finally:
            self.tiempos_ms[nombre] = (self._reloj() - inicio) * 1000.0

    @contextmanager
    def total(self):
        if self._en_total or self.total_ms is not None:
            raise ValueError("El total solo se mide una vez.")
        self._en_total = True
        inicio = self._reloj()
        try:
            yield
        finally:
            self.total_ms = (self._reloj() - inicio) * 1000.0
            self._en_total = False

    @property
    def suma_etapas_ms(self) -> float:
        return sum(self.tiempos_ms.values())

    @property
    def sobrecarga_ms(self) -> float | None:
        """Tiempo del total no atribuido a ninguna etapa (None si no hay total)."""
        return None if self.total_ms is None else self.total_ms - self.suma_etapas_ms

    def como_dict(self, etapas: tuple[str, ...] = (), decimales: int = 3) -> dict:
        """Tiempos redondeados. Las etapas esperadas que no llegaron a ejecutarse quedan en None."""
        nombres = list(etapas) + [n for n in self.tiempos_ms if n not in etapas]
        return {
            "tiempos_ms": {n: (round(self.tiempos_ms[n], decimales) if n in self.tiempos_ms else None) for n in nombres},
            "tiempo_total_ms": None if self.total_ms is None else round(self.total_ms, decimales),
            "sobrecarga_ms": None if self.sobrecarga_ms is None else round(self.sobrecarga_ms, decimales),
            "etapas_fallidas": list(self.etapas_fallidas),
        }
