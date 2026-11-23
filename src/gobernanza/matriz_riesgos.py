"""Matriz de riesgos del proyecto (Bloque 32, Misión 3).

Fórmula y cortes OFICIALES del curso (no se modifican):
    puntaje = probabilidad * impacto
    >= 15 CRITICO · >= 9 ALTO · >= 4 MEDIO · resto BAJO

Probabilidad e impacto se guardan en `data/gobernanza/matriz_riesgos.json` con su justificación;
el puntaje, la categoría y la sensibilidad al límite se CALCULAN siempre (no se almacenan).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.rag.configuracion import RAIZ_REPO

RUTA_MATRIZ = RAIZ_REPO / "data" / "gobernanza" / "matriz_riesgos.json"
ESTADOS_CONTROL = ("implementado_probado", "implementado_sin_prueba", "documentado_pendiente", "propuesto")
CATEGORIAS_CON_SUPERVISION = ("ALTO", "CRITICO")
CAMPOS_TEXTO = ("id", "riesgo", "justificacion_probabilidad", "justificacion_impacto", "mitigacion_existente",
                "limitaciones", "estado_control")


class MatrizInvalidaError(ValueError):
    pass


def validar_valor(valor, nombre: str = "valor") -> int:
    """Entero 1–5. Los booleanos se rechazan aunque `bool` sea subclase de `int`."""
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 5:
        raise ValueError(f"{nombre} debe ser un entero entre 1 y 5; se recibió {valor!r}.")
    return valor


def categoria_riesgo(puntaje: int) -> str:
    if puntaje >= 15:
        return "CRITICO"
    if puntaje >= 9:
        return "ALTO"
    if puntaje >= 4:
        return "MEDIO"
    return "BAJO"


def calcular_puntaje(probabilidad: int, impacto: int) -> int:
    return validar_valor(probabilidad, "probabilidad") * validar_valor(impacto, "impacto")


def vecinos_que_cambian(probabilidad: int, impacto: int) -> list[dict]:
    """Cambios de ±1 en UNA sola variable (sin salir de 1–5) que alteran la categoría."""
    base = categoria_riesgo(calcular_puntaje(probabilidad, impacto))
    cambios = []
    for variable, delta in (("probabilidad", -1), ("probabilidad", 1), ("impacto", -1), ("impacto", 1)):
        p = probabilidad + delta if variable == "probabilidad" else probabilidad
        i = impacto + delta if variable == "impacto" else impacto
        if not (1 <= p <= 5 and 1 <= i <= 5):
            continue
        categoria = categoria_riesgo(p * i)
        if categoria != base:
            cambios.append({"variable": variable, "delta": delta, "probabilidad": p, "impacto": i,
                            "puntaje": p * i, "categoria": categoria})
    return cambios


def esta_en_el_limite(probabilidad: int, impacto: int) -> bool:
    return bool(vecinos_que_cambian(probabilidad, impacto))


@dataclass(frozen=True)
class Riesgo:
    id: str
    riesgo: str
    evidencia: list
    probabilidad: int
    justificacion_probabilidad: str
    impacto: int
    justificacion_impacto: str
    mitigacion_existente: str
    limitaciones: str
    supervision: dict
    estado_control: str
    bloques: list

    @property
    def puntaje(self) -> int:
        return calcular_puntaje(self.probabilidad, self.impacto)

    @property
    def categoria(self) -> str:
        return categoria_riesgo(self.puntaje)

    @property
    def al_limite(self) -> bool:
        return esta_en_el_limite(self.probabilidad, self.impacto)

    def como_dict(self) -> dict:
        return {**self.__dict__, "puntaje": self.puntaje, "categoria": self.categoria, "al_limite": self.al_limite,
                "cambios_de_categoria": vecinos_que_cambian(self.probabilidad, self.impacto)}


def riesgo_desde_dict(datos: dict, raiz: Path = RAIZ_REPO) -> Riesgo:
    if not isinstance(datos, dict):
        raise MatrizInvalidaError("Cada riesgo debe ser un objeto.")
    for campo in CAMPOS_TEXTO:
        if not isinstance(datos.get(campo), str) or not datos[campo].strip():
            raise MatrizInvalidaError(f"{datos.get('id', '?')}: falta '{campo}'.")
    for campo in ("puntaje", "categoria"):
        if campo in datos:
            raise MatrizInvalidaError(f"{datos['id']}: '{campo}' se calcula; no debe almacenarse.")
    try:
        validar_valor(datos.get("probabilidad"), "probabilidad")
        validar_valor(datos.get("impacto"), "impacto")
    except ValueError as error:
        raise MatrizInvalidaError(f"{datos['id']}: {error}") from error
    if datos["estado_control"] not in ESTADOS_CONTROL:
        raise MatrizInvalidaError(f"{datos['id']}: estado_control desconocido {datos['estado_control']!r}.")
    evidencia = datos.get("evidencia")
    if not isinstance(evidencia, list) or not evidencia:
        raise MatrizInvalidaError(f"{datos['id']}: necesita evidencia.")
    for item in evidencia:
        if not isinstance(item, dict) or not (raiz / item.get("ruta", "")).exists() or not item.get("detalle"):
            raise MatrizInvalidaError(f"{datos['id']}: evidencia inexistente o sin detalle: {item!r}.")
    supervision = datos.get("supervision")
    if not isinstance(supervision, dict) or not supervision.get("control") \
            or supervision.get("estado") not in ESTADOS_CONTROL:
        raise MatrizInvalidaError(f"{datos['id']}: 'supervision' debe tener control y estado válidos.")
    if not isinstance(datos.get("bloques"), list) or not datos["bloques"]:
        raise MatrizInvalidaError(f"{datos['id']}: indica los bloques relacionados.")
    return Riesgo(**{k: datos[k] for k in Riesgo.__dataclass_fields__})


def cargar_matriz(ruta: Path | str = RUTA_MATRIZ, raiz: Path = RAIZ_REPO) -> list[Riesgo]:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MatrizInvalidaError(f"{ruta} no es JSON válido: {error}") from error
    riesgos = [riesgo_desde_dict(r, raiz) for r in datos.get("riesgos", [])]
    ids = [r.id for r in riesgos]
    if len(ids) != len(set(ids)):
        raise MatrizInvalidaError("IDs de riesgo repetidos.")
    if len(riesgos) < 5:
        raise MatrizInvalidaError(f"La matriz necesita al menos 5 riesgos; tiene {len(riesgos)}.")
    return riesgos


def ordenar(riesgos: list[Riesgo]) -> list[Riesgo]:
    """Puntaje descendente; a igual puntaje, mayor impacto primero; luego por ID."""
    return sorted(riesgos, key=lambda r: (-r.puntaje, -r.impacto, r.id))


def sin_supervision_requerida(riesgos: list[Riesgo]) -> list[str]:
    """IDs ALTO/CRITICO sin un control humano identificado (debe quedar vacío)."""
    return [r.id for r in riesgos if r.categoria in CATEGORIAS_CON_SUPERVISION
            and not (r.supervision.get("control") and r.supervision.get("estado") in ESTADOS_CONTROL)]


def tabla_markdown(riesgos: list[Riesgo]) -> str:
    filas = ["| ID | Riesgo | P | I | Puntaje | Categoría | Al límite | Supervisión humana | Estado del control |",
             "|---|---|---:|---:|---:|---|---|---|---|"]
    for r in ordenar(riesgos):
        limite = "Sí: " + "; ".join(f"{c['variable']} {c['delta']:+d} → {c['categoria']}"
                                    for c in vecinos_que_cambian(r.probabilidad, r.impacto)) if r.al_limite else "No"
        filas.append(f"| {r.id} | {r.riesgo} | {r.probabilidad} | {r.impacto} | {r.puntaje} | {r.categoria} | {limite} | "
                     f"{r.supervision['control']} ({r.supervision['estado']}) | {r.estado_control} |")
    return "\n".join(filas)
