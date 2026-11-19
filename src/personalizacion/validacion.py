"""Validación del dataset de personalización (Bloque 29).

`validar_dataset` recorre TODOS los ejemplos y devuelve todos los problemas en una sola pasada:
nunca se detiene en el primer error. Los problemas tienen nivel "error" (el ejemplo no sirve para
entrenar) o "advertencia" (conviene revisarlo, pero no invalida el dataset).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

from src.personalizacion.dataset import CATEGORIAS, CLAVES_EJEMPLO, CLAVES_SALIDA, REGLAS_COHERENCIA, normalizar

ERROR, ADVERTENCIA = "error", "advertencia"
UMBRAL_SIMILITUD = 0.85  # Heurística didáctica (difflib) para avisar de entradas casi iguales.


@dataclass(frozen=True)
class Problema:
    nivel: str
    codigo: str
    mensaje: str
    indices: tuple[int, ...] = ()

    def __str__(self) -> str:
        donde = f" [índices {', '.join(map(str, self.indices))}]" if self.indices else ""
        return f"{self.nivel.upper()} {self.codigo}{donde}: {self.mensaje}"


def revisar_coherencia(categoria: str, accion: str) -> tuple[list[str], bool]:
    """Devuelve (términos contradictorios encontrados, ¿aparece algún término esperado?)."""
    reglas = REGLAS_COHERENCIA.get(categoria)
    if reglas is None:
        return [], True
    texto = normalizar(accion)
    contradicciones = [p for p in reglas["prohibidos"] if re.search(p, texto)]
    relacionada = any(re.search(p, texto) for p in reglas["esperados"])
    return contradicciones, relacionada


def validar_salida(texto: Any, categorias: Iterable[str] = CATEGORIAS) -> tuple[dict | None, list[tuple[str, str]]]:
    """Valida una salida (texto JSON). Devuelve (dict o None, [(codigo, mensaje), ...]) con TODOS los fallos.

    Se usa tanto para el dataset como para evaluar respuestas de un modelo.
    """
    categorias = tuple(categorias)
    fallos: list[tuple[str, str]] = []
    if not isinstance(texto, str):
        return None, [("tipo_salida", f"la salida debe ser texto JSON, no {type(texto).__name__}")]
    if not texto.strip():
        return None, [("salida_vacia", "la salida está vacía")]
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as error:
        return None, [("json_malformado", f"JSON inválido: {error.msg} (posición {error.pos})")]
    if not isinstance(datos, dict):
        return None, [("json_no_objeto", f"el JSON debe ser un objeto, no {type(datos).__name__}")]

    for clave in CLAVES_SALIDA:
        if clave not in datos:
            fallos.append(("clave_faltante", f"falta la clave {clave!r}"))
    for clave in datos:
        if clave not in CLAVES_SALIDA:
            fallos.append(("clave_inesperada", f"clave no permitida {clave!r}"))

    categoria = datos.get("categoria")
    categoria_valida = False
    if "categoria" in datos:
        if not isinstance(categoria, str):
            fallos.append(("tipo_categoria", f"categoria debe ser texto, no {type(categoria).__name__}"))
        elif categoria not in categorias:
            fallos.append(("categoria_desconocida", f"categoría {categoria!r} fuera de {list(categorias)}"))
        else:
            categoria_valida = True

    accion = datos.get("accion_sugerida")
    accion_valida = False
    if "accion_sugerida" in datos:
        if not isinstance(accion, str):
            fallos.append(("tipo_accion", f"accion_sugerida debe ser texto, no {type(accion).__name__}"))
        elif not accion.strip():
            fallos.append(("accion_vacia", "accion_sugerida está vacía"))
        else:
            accion_valida = True

    if categoria_valida and accion_valida:
        contradicciones, _ = revisar_coherencia(categoria, accion)
        if contradicciones:
            fallos.append(("contradiccion", f"la acción contradice la categoría {categoria!r} "
                                            f"(patrones: {contradicciones})"))
    return datos, fallos


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def validar_dataset(
    ejemplos: Any,
    categorias: Iterable[str] = CATEGORIAS,
    umbral_similitud: float = UMBRAL_SIMILITUD,
) -> list[Problema]:
    """Valida el dataset completo y devuelve todos los problemas (lista vacía si no hay ninguno)."""
    categorias = tuple(categorias)
    problemas: list[Problema] = []
    if not isinstance(ejemplos, list):
        return [Problema(ERROR, "dataset_no_lista", f"el dataset debe ser una lista, no {type(ejemplos).__name__}")]
    if not ejemplos:
        return [Problema(ERROR, "dataset_vacio", "el dataset no tiene ejemplos")]

    entradas_validas: dict[int, str] = {}
    registros_vistos: dict[str, int] = {}

    for i, ejemplo in enumerate(ejemplos):
        if not isinstance(ejemplo, dict):
            problemas.append(Problema(ERROR, "tipo_ejemplo", f"cada ejemplo debe ser un objeto, no {type(ejemplo).__name__}", (i,)))
            continue
        for clave in CLAVES_EJEMPLO:
            if clave not in ejemplo:
                problemas.append(Problema(ERROR, "clave_ejemplo_faltante", f"falta {clave!r}", (i,)))
        for clave in ejemplo:
            if clave not in CLAVES_EJEMPLO:
                problemas.append(Problema(ERROR, "clave_ejemplo_inesperada", f"clave no permitida {clave!r}", (i,)))

        if "entrada" in ejemplo:
            entrada = ejemplo["entrada"]
            if not isinstance(entrada, str):
                problemas.append(Problema(ERROR, "tipo_entrada", f"la entrada debe ser texto, no {type(entrada).__name__}", (i,)))
            elif not entrada.strip():
                problemas.append(Problema(ERROR, "entrada_vacia", "la entrada está vacía", (i,)))
            else:
                entradas_validas[i] = normalizar(entrada)

        if "salida" in ejemplo:
            datos, fallos = validar_salida(ejemplo["salida"], categorias)
            for codigo, mensaje in fallos:
                problemas.append(Problema(ERROR, codigo, mensaje, (i,)))
            if datos is not None and not fallos:
                _, relacionada = revisar_coherencia(datos["categoria"], datos["accion_sugerida"])
                if not relacionada:
                    problemas.append(Problema(ADVERTENCIA, "accion_poco_relacionada",
                                              f"la acción no menciona términos típicos de {datos['categoria']!r}", (i,)))

        try:
            firma = json.dumps(ejemplo, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            firma = repr(ejemplo)
        if firma in registros_vistos:
            problemas.append(Problema(ERROR, "registro_identico", "registro idéntico a otro", (registros_vistos[firma], i)))
        else:
            registros_vistos[firma] = i

    # Entradas duplicadas (misma entrada normalizada), con la misma o distinta salida.
    primera_por_entrada: dict[str, int] = {}
    for i, entrada in entradas_validas.items():
        if entrada in primera_por_entrada:
            j = primera_por_entrada[entrada]
            mismo_registro = ejemplos[i] == ejemplos[j]
            if not mismo_registro:
                misma_salida = ejemplos[i].get("salida") == ejemplos[j].get("salida")
                detalle = "con la misma salida" if misma_salida else "con salidas DISTINTAS (etiqueta contradictoria)"
                problemas.append(Problema(ERROR, "entrada_duplicada", f"entrada repetida {detalle}", (j, i)))
        else:
            primera_por_entrada[entrada] = i

    problemas.extend(advertir_similares(entradas_validas, umbral_similitud))
    return problemas


def advertir_similares(entradas: dict[int, str], umbral: float = UMBRAL_SIMILITUD) -> list[Problema]:
    """Advertencias para pares de entradas distintas pero muy parecidas (ratio de difflib >= umbral)."""
    avisos = []
    items = sorted(entradas.items())
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            (i, ti), (j, tj) = items[a], items[b]
            if ti == tj:
                continue  # Ya reportado como duplicado.
            ratio = _similitud(ti, tj)
            if ratio >= umbral:
                avisos.append(Problema(ADVERTENCIA, "entradas_muy_parecidas", f"similitud {ratio:.2f}", (i, j)))
    return avisos


def solapamiento(entrenamiento: list[dict], validacion: list[dict], umbral: float = UMBRAL_SIMILITUD) -> list[Problema]:
    """Fugas entre conjuntos: entradas de validación idénticas (error) o muy parecidas (advertencia) a las de entrenamiento."""
    problemas = []
    textos_e = {i: normalizar(e["entrada"]) for i, e in enumerate(entrenamiento)
                if isinstance(e, dict) and isinstance(e.get("entrada"), str)}
    for j, ejemplo in enumerate(validacion):
        if not isinstance(ejemplo, dict) or not isinstance(ejemplo.get("entrada"), str):
            continue
        tv = normalizar(ejemplo["entrada"])
        for i, te in textos_e.items():
            if tv == te:
                problemas.append(Problema(ERROR, "fuga_validacion",
                                          f"la entrada de validación {j} está también en entrenamiento ({i})", (i, j)))
            else:
                ratio = _similitud(tv, te)
                if ratio >= umbral:
                    problemas.append(Problema(ADVERTENCIA, "validacion_parecida_a_entrenamiento",
                                              f"validación {j} ~ entrenamiento {i} (similitud {ratio:.2f})", (i, j)))
    return problemas


def errores(problemas: Iterable[Problema]) -> list[Problema]:
    return [p for p in problemas if p.nivel == ERROR]


def advertencias(problemas: Iterable[Problema]) -> list[Problema]:
    return [p for p in problemas if p.nivel == ADVERTENCIA]
