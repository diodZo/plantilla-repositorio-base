"""Método de decisión del Bloque 30: RAG vs fine-tuning completo vs PEFT.

Cinco criterios booleanos suman puntos a las estrategias según `PESOS` (pesos oficiales del PDF
del Bloque 30). Un criterio puede quedar `None` (no verificado): no suma puntos, NO se trata como
`False` y se informa aparte; mientras haya alguno, el puntaje es PROVISIONAL. Los empates se
devuelven completos: nunca se elige la primera clave de un diccionario.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product
from pathlib import Path
from typing import Any

from src.personalizacion.dataset import CATEGORIAS, CLAVES_SALIDA, RAIZ_REPO

ESTRATEGIAS: tuple[str, ...] = ("RAG", "Fine-tuning completo", "PEFT")

CRITERIOS: dict[str, str] = {
    "informacion_cambia_seguido": "La información cambia al menos mensualmente.",
    "problema_de_formato_o_tono": "≥ 15 % de incumplimiento de formato o tono en una muestra de 20 respuestas.",
    "dataset_grande_y_de_calidad": "≥ 200 ejemplos etiquetados y revisión satisfactoria de 20.",
    "presupuesto_limitado_o_iterar_rapido": "Restricciones de presupuesto o necesidad real de iterar rápido.",
    "necesita_multiples_variantes": "Se necesita más de una variante personalizada.",
}

# Pesos oficiales del material del Bloque 30.
PESOS: dict[str, dict[str, int]] = {
    "informacion_cambia_seguido": {"RAG": 3, "Fine-tuning completo": 0, "PEFT": 0},
    "problema_de_formato_o_tono": {"RAG": 0, "Fine-tuning completo": 1, "PEFT": 2},
    "dataset_grande_y_de_calidad": {"RAG": 0, "Fine-tuning completo": 2, "PEFT": 1},
    "presupuesto_limitado_o_iterar_rapido": {"RAG": 2, "Fine-tuning completo": 0, "PEFT": 1},
    "necesita_multiples_variantes": {"RAG": 0, "Fine-tuning completo": 0, "PEFT": 2},
}

EJEMPLO_OFICIAL_CURSO: dict[str, bool] = {
    "informacion_cambia_seguido": False,
    "problema_de_formato_o_tono": True,
    "dataset_grande_y_de_calidad": True,
    "presupuesto_limitado_o_iterar_rapido": False,
    "necesita_multiples_variantes": False,
}

HIPOTESIS_INICIAL: dict[str, bool] = {
    "informacion_cambia_seguido": False,
    "problema_de_formato_o_tono": True,
    "dataset_grande_y_de_calidad": False,
    "presupuesto_limitado_o_iterar_rapido": True,
    "necesita_multiples_variantes": False,
}

# Umbrales del curso (orientativos; no son requisitos oficiales de la API).
UMBRAL_INCUMPLIMIENTO = 0.15
MUESTRA_FORMATO = 20
MINIMO_EJEMPLOS_CURSO = 200
REVISION_MANUAL = 20
VENTANA_DIAS = 30

ARCHIVOS_CATALOGO_ERRORES = ("src/cliente.py", "src/rag/reintentos.py", "src/rag/errores.py")
RUTA_RESPUESTAS_BASE = RAIZ_REPO / "data" / "personalizacion" / "respuestas_modelo_base.json"
INDICIOS_PRESUPUESTO = (
    ("src/indexar_corpus.py", "respetar la cuota por minuto"),
    ("docs/README-bloque24.md", "cuota gratuita de embeddings limita"),
    ("docs/README-bloque28.md", "errores 429 de cuota *free tier*"),
)

VERIFICADO, PARCIAL, NO_VERIFICADO = "verificado", "verificado_parcial", "no_verificado"


@dataclass(frozen=True)
class Evidencia:
    criterio: str
    valor: bool | None
    estado: str
    detalle: str


@dataclass
class ResultadoDecision:
    puntos: dict[str, int]
    empatadas: list[str]
    no_verificados: list[str] = field(default_factory=list)
    maximo_posible: dict[str, int] = field(default_factory=dict)

    @property
    def ganadora(self) -> str | None:
        """Solo hay ganadora si nadie empata en el primer lugar."""
        return self.empatadas[0] if len(self.empatadas) == 1 else None

    @property
    def hay_empate(self) -> bool:
        return len(self.empatadas) > 1

    @property
    def provisional(self) -> bool:
        """Hay criterios sin verificar: el puntaje no es una decisión final fundamentada."""
        return bool(self.no_verificados)


def puntuar(valores: dict[str, bool | None]) -> ResultadoDecision:
    """Suma los puntos de cada estrategia. Exige exactamente los cinco criterios."""
    faltan = set(CRITERIOS) - set(valores)
    sobran = set(valores) - set(CRITERIOS)
    if faltan or sobran:
        raise ValueError(f"Criterios inválidos. Faltan: {sorted(faltan)}; desconocidos: {sorted(sobran)}.")
    for nombre, valor in valores.items():
        if valor is not None and not isinstance(valor, bool):
            raise TypeError(f"{nombre} debe ser True, False o None, no {valor!r}.")

    puntos = {e: 0 for e in ESTRATEGIAS}
    maximo_posible = {e: 0 for e in ESTRATEGIAS}
    for nombre, valor in valores.items():
        for estrategia, peso in PESOS[nombre].items():
            if valor is True:
                puntos[estrategia] += peso
            if valor is not False:
                maximo_posible[estrategia] += peso
    mejor = max(puntos.values())
    return ResultadoDecision(
        puntos=puntos,
        empatadas=[e for e in ESTRATEGIAS if puntos[e] == mejor],
        no_verificados=[n for n, v in valores.items() if v is None],
        maximo_posible=maximo_posible,
    )


def escenarios_no_verificados(valores: dict[str, bool | None]) -> list[tuple[dict[str, bool], ResultadoDecision]]:
    """Puntúa cada combinación posible de los criterios `None` (análisis; no cambia la regla de puntuación)."""
    pendientes = [n for n, v in valores.items() if v is None]
    escenarios = []
    for combinacion in product((True, False), repeat=len(pendientes)):
        asignacion = dict(zip(pendientes, combinacion))
        escenarios.append((asignacion, puntuar({**valores, **asignacion})))
    return escenarios


def sensibilidad(valores: dict[str, bool | None]) -> list[tuple[str, bool | None, bool, ResultadoDecision]]:
    """Cambia cada criterio por separado: (criterio, valor original, valor probado, resultado).

    Un criterio booleano se invierte; uno `None` se prueba con True y con False.
    """
    filas = []
    for nombre, valor in valores.items():
        alternativas = (True, False) if valor is None else (not valor,)
        for alternativo in alternativas:
            filas.append((nombre, valor, alternativo, puntuar({**valores, nombre: alternativo})))
    return filas


# --- Evidencia del repositorio --------------------------------------------------------------

def _git(args: list[str], raiz: Path) -> str | None:
    try:
        proceso = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proceso.stdout if proceso.returncode == 0 else None


def fechas_git(raiz: Path = RAIZ_REPO) -> tuple[list[date], date | None, date | None] | None:
    """(fechas de commits del catálogo de errores, primer commit del repo, fecha de HEAD) o None sin git."""
    catalogo = _git(["log", "--format=%ad", "--date=short", "--", *ARCHIVOS_CATALOGO_ERRORES], raiz)
    todas = _git(["log", "--format=%ad", "--date=short"], raiz)
    if catalogo is None or todas is None:
        return None
    fechas_repo = [date.fromisoformat(l) for l in todas.split()]
    if not fechas_repo:
        return None
    return [date.fromisoformat(l) for l in catalogo.split()], min(fechas_repo), max(fechas_repo)


def evidencia_informacion(fechas_catalogo: list[date] | None, inicio: date | None, referencia: date | None) -> Evidencia:
    nombre = "informacion_cambia_seguido"
    if fechas_catalogo is None or inicio is None or referencia is None:
        return Evidencia(nombre, None, NO_VERIFICADO, "No se pudo leer el historial de git.")
    historial = (referencia - inicio).days
    if historial < VENTANA_DIAS:
        return Evidencia(nombre, None, NO_VERIFICADO,
                         f"El historial abarca {historial} días; hace falta al menos {VENTANA_DIAS} para opinar.")
    recientes = sorted(d for d in fechas_catalogo if referencia - timedelta(days=VENTANA_DIAS) < d <= referencia)
    archivos = ", ".join(f"`{a}`" for a in ARCHIVOS_CATALOGO_ERRORES)
    detalle = (f"El catálogo de errores y acciones ({archivos}) cambió en {len(recientes)} commit{'' if len(recientes) == 1 else 's'} durante los "
               f"{VENTANA_DIAS} días previos a HEAD ({referencia.isoformat()})"
               + (f": {', '.join(d.isoformat() for d in recientes)}" if recientes else "")
               + f". Historial total del repositorio: {historial} días.")
    estado = VERIFICADO if historial >= 3 * VENTANA_DIAS else PARCIAL
    if estado == PARCIAL:
        detalle += " Ventana corta y proyecto en desarrollo activo: no demuestra una frecuencia sostenida."
    return Evidencia(nombre, bool(recientes), estado, detalle)


def tasa_incumplimiento_formato(respuestas: list[Any]) -> float:
    from src.personalizacion.validacion import validar_salida

    fallidas = sum(1 for r in respuestas if validar_salida(r, CATEGORIAS)[1])
    return fallidas / len(respuestas)


def evidencia_formato(ruta: Path = RUTA_RESPUESTAS_BASE) -> Evidencia:
    nombre = "problema_de_formato_o_tono"
    if not Path(ruta).is_file():
        return Evidencia(nombre, None, NO_VERIFICADO,
                         f"No existe una muestra de respuestas reales del modelo base ({Path(ruta).name}). "
                         "No se calcula ni se supone un porcentaje de incumplimiento.")
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    respuestas = datos.get("respuestas", []) if isinstance(datos, dict) else datos
    origen = datos.get("origen", "sin origen declarado") if isinstance(datos, dict) else "sin origen declarado"
    if len(respuestas) < MUESTRA_FORMATO:
        return Evidencia(nombre, None, NO_VERIFICADO,
                         f"La muestra tiene {len(respuestas)} respuestas; el criterio exige {MUESTRA_FORMATO}.")
    tasa = tasa_incumplimiento_formato(respuestas)
    return Evidencia(nombre, tasa >= UMBRAL_INCUMPLIMIENTO, VERIFICADO,
                     f"{tasa:.0%} de incumplimiento de formato en {len(respuestas)} respuestas (origen: {origen}). "
                     "El tono no se mide automáticamente.")


def evidencia_dataset(n_ejemplos: int, revision_satisfactoria: bool | None = None) -> Evidencia:
    nombre = "dataset_grande_y_de_calidad"
    if n_ejemplos < MINIMO_EJEMPLOS_CURSO:
        return Evidencia(nombre, False, VERIFICADO,
                         f"Hay {n_ejemplos} ejemplos etiquetados; el criterio del curso pide al menos {MINIMO_EJEMPLOS_CURSO}.")
    if revision_satisfactoria is None:
        return Evidencia(nombre, None, NO_VERIFICADO,
                         f"Hay {n_ejemplos} ejemplos, pero falta la revisión manual de {REVISION_MANUAL}.")
    return Evidencia(nombre, revision_satisfactoria, VERIFICADO,
                     f"{n_ejemplos} ejemplos; revisión manual de {REVISION_MANUAL}: "
                     f"{'satisfactoria' if revision_satisfactoria else 'no satisfactoria'}.")


def evidencia_presupuesto(raiz: Path = RAIZ_REPO) -> Evidencia:
    nombre = "presupuesto_limitado_o_iterar_rapido"
    encontrados = []
    for relativa, marca in INDICIOS_PRESUPUESTO:
        ruta = raiz / relativa
        if ruta.is_file() and marca in ruta.read_text(encoding="utf-8"):
            encontrados.append(f"`{relativa}` («{marca}»)")
    if not encontrados:
        return Evidencia(nombre, None, NO_VERIFICADO, "No se encontraron indicios de restricciones de cuota o presupuesto.")
    return Evidencia(nombre, True, PARCIAL,
                     "Indicios indirectos de operar con cuota limitada: " + "; ".join(encontrados)
                     + ". No hay un presupuesto monetario documentado.")


def evidencia_variantes() -> Evidencia:
    return Evidencia("necesita_multiples_variantes", False, PARCIAL,
                     f"La tarea define un único esquema de salida {list(CLAVES_SALIDA)} y no hay en el repositorio "
                     "ningún requisito de una segunda variante (otro idioma, tono o cliente).")


def recopilar_evidencia(n_ejemplos: int, raiz: Path = RAIZ_REPO, ruta_respuestas: Path = RUTA_RESPUESTAS_BASE,
                        fechas: tuple | None = None) -> list[Evidencia]:
    fechas = fechas if fechas is not None else fechas_git(raiz)
    catalogo, inicio, referencia = fechas if fechas else (None, None, None)
    return [
        evidencia_informacion(catalogo, inicio, referencia),
        evidencia_formato(ruta_respuestas),
        evidencia_dataset(n_ejemplos),
        evidencia_presupuesto(raiz),
        evidencia_variantes(),
    ]


def valores_de(evidencias: list[Evidencia]) -> dict[str, bool | None]:
    return {e.criterio: e.valor for e in evidencias}


def recomendar(resultado: ResultadoDecision) -> dict[str, Any]:
    """Recomendación según el resultado. El método puntúa RAG/FT/PEFT; Prompt + Pydantic es la línea base."""
    formato_pendiente = "problema_de_formato_o_tono" in resultado.no_verificados
    futura_peft = ("PEFT, solo si la línea base incumple el formato en ≥ 15 % de una muestra de 20 "
                   "y se reúnen los datos y la infraestructura necesarios")
    if resultado.ganadora == "RAG":
        return {
            "inmediata": "Prompt + Pydantic, con el catálogo de errores como contexto externo y actualizable "
                         "(el principio que puntúa RAG, sin índice vectorial)",
            "futura": futura_peft,
            "motivo": ("RAG lidera" + (" de forma provisional" if resultado.provisional else "")
                       + " por los criterios de información cambiante y presupuesto; ambos se satisfacen "
                       "manteniendo el catálogo fuera de los pesos del modelo, y el catálogo es pequeño, así que "
                       "no hace falta recuperación sobre un corpus. RAG no resuelve el formato, que es el "
                       "problema planteado: eso lo cubre la validación Pydantic"
                       + ("; el criterio de formato sigue sin medirse" if formato_pendiente else "")),
        }
    if resultado.hay_empate or formato_pendiente:
        return {
            "inmediata": "Prompt + Pydantic (salida estructurada validada)",
            "futura": futura_peft,
            "motivo": ("el método " + ("termina en empate entre " + " y ".join(resultado.empatadas)
                                      if resultado.hay_empate else f"favorece a {resultado.ganadora}")
                       + (" y el criterio decisivo de formato no está medido" if formato_pendiente else "")),
        }
    return {"inmediata": "Prompt + Pydantic como control",
            "futura": f"{resultado.ganadora}, si el control incumple el formato en ≥ 15 %",
            "motivo": f"gana {resultado.ganadora} sin empate y con el formato medido"}
