"""Genera `docs/decision_personalizacion.md` a partir de datos calculados (Bloque 30).

El documento tiene exactamente cuatro secciones principales (`## `). Todas las cifras vienen de
los argumentos; los únicos valores fijos son supuestos declarados como tales (tiempos de etiquetado).
"""
from __future__ import annotations

import math
from typing import Any

from src.personalizacion.decision import (
    CRITERIOS, EJEMPLO_OFICIAL_CURSO, ESTRATEGIAS, HIPOTESIS_INICIAL, MINIMO_EJEMPLOS_CURSO, MUESTRA_FORMATO, PARCIAL,
    PESOS, REVISION_MANUAL, UMBRAL_INCUMPLIMIENTO, Evidencia, ResultadoDecision, escenarios_no_verificados, puntuar,
    recomendar, sensibilidad, valores_de,
)

SECCIONES = ("## 1. El problema", "## 2. Resultado del método de decisión",
             "## 3. Técnica elegida y por qué", "## 4. Qué necesitaríamos para ejecutarla")

# SUPUESTOS (no medidos): minutos por persona para redactar y revisar un ejemplo nuevo.
MINUTOS_POR_EJEMPLO_SUPUESTO = 2
MINUTOS_REVISION_SUPUESTO = 3


def _si_no(valor: bool | None) -> str:
    return {True: "Sí", False: "No", None: "No verificado"}[valor]


def _tabla_puntos(resultado: ResultadoDecision, con_maximo: bool) -> list[str]:
    cabecera = "| Estrategia | Puntos |" + (" Máximo si los no verificados fueran «Sí» |" if con_maximo else "")
    separador = "|---|---|" + ("---|" if con_maximo else "")
    filas = [cabecera, separador]
    for e in ESTRATEGIAS:
        filas.append(f"| {e} | {resultado.puntos[e]} |" + (f" {resultado.maximo_posible[e]} |" if con_maximo else ""))
    return filas


def _puntos(n: int) -> str:
    return f"{n} punto" if n == 1 else f"{n} puntos"


def _empate(resultado: ResultadoDecision) -> str:
    if resultado.hay_empate:
        return f"**Empate en el primer lugar:** {', '.join(resultado.empatadas)} ({_puntos(resultado.puntos[resultado.empatadas[0]])})."
    return f"**Primer lugar sin empate:** {resultado.ganadora} ({_puntos(resultado.puntos[resultado.ganadora])})."


def _primer_lugar(resultado: ResultadoDecision) -> str:
    return " / ".join(resultado.empatadas) + (" (empate)" if resultado.hay_empate else "")


def _puntos_cortos(resultado: ResultadoDecision) -> str:
    return " · ".join(f"{e} {resultado.puntos[e]}" for e in ESTRATEGIAS)


def _lineas_escenarios(valores: dict[str, bool | None]) -> list[str]:
    escenarios = escenarios_no_verificados(valores)
    if not any(asignacion for asignacion, _ in escenarios):
        return []
    lineas = ["Qué pasaría con cada valor posible de los criterios no verificados:", "",
              "| Supuesto | Puntos | Primer lugar |", "|---|---|---|"]
    for asignacion, r in escenarios:
        supuesto = ", ".join(f"`{c}` = {_si_no(v)}" for c, v in asignacion.items())
        lineas.append(f"| {supuesto} | {_puntos_cortos(r)} | {_primer_lugar(r)} |")
    primeros = {tuple(r.empatadas) for _, r in escenarios}
    lineas += ["", "El primer lugar **no depende** de los criterios no verificados." if len(primeros) == 1
               else "El primer lugar **depende** de los criterios no verificados.", ""]
    return lineas


def _lineas_sensibilidad(valores: dict[str, bool | None], ev: dict[str, Evidencia]) -> list[str]:
    lineas = ["Sensibilidad (cambiando un solo criterio cada vez respecto de los valores comprobados):", "",
              "| Criterio cambiado | De → a | Puntos | Primer lugar |", "|---|---|---|---|"]
    for nombre, original, alternativo, r in sensibilidad(valores):
        marca = " (comprobación parcial)" if ev[nombre].estado == PARCIAL else ""
        lineas.append(f"| `{nombre}`{marca} | {_si_no(original)} → {_si_no(alternativo)} | {_puntos_cortos(r)} | "
                      f"{_primer_lugar(r)} |")
    lineas.append("")
    return lineas


def _texto_infraestructura(sdk: dict[str, Any], compatibilidad: dict[str, dict[str, Any]]) -> str:
    inline = compatibilidad.get("ejemplos inline", {})
    gcs = compatibilidad.get("dataset en Cloud Storage", {})
    version = sdk.get("version", "desconocida")
    if (inline.get("verificable") and gcs.get("verificable") and inline["gemini_developer_api"] is not None
            and inline["vertex"] is not None and gcs["vertex"] is None):
        return (f"con google-genai {version}, el SDK solo acepta PEFT (`tuning_mode`, `adapter_size`) en modo Vertex y "
                "con el dataset en Cloud Storage; rechaza la combinación con ejemplos inline en ambos modos. El proyecto "
                "usa una clave de la API de Gemini (modo Developer API), donde esos parámetros se rechazan")
    return f"con google-genai {version}, la compatibilidad de PEFT no quedó confirmada localmente (ver sección 4)"


def generar_documento(
    *,
    conteos_entrenamiento: dict[str, int],
    conteos_validacion: dict[str, int],
    evidencias: list[Evidencia],
    resultado: ResultadoDecision,
    resultado_hipotesis: ResultadoDecision,
    sdk: dict[str, Any],
    compatibilidad: dict[str, dict[str, Any]],
    referencia_git: str,
) -> str:
    n_ent = sum(conteos_entrenamiento.values())
    n_val = sum(conteos_validacion.values())
    n_total = n_ent + n_val
    categorias = list(conteos_entrenamiento)
    por_categoria_objetivo = math.ceil(MINIMO_EJEMPLOS_CURSO / len(categorias))
    faltan = max(0, MINIMO_EJEMPLOS_CURSO - n_total)
    minutos = faltan * MINUTOS_POR_EJEMPLO_SUPUESTO + REVISION_MANUAL * MINUTOS_REVISION_SUPUESTO
    rec = recomendar(resultado)
    ev = {e.criterio: e for e in evidencias}
    valores = valores_de(evidencias)
    ejemplo_oficial = puntuar(EJEMPLO_OFICIAL_CURSO)
    totales = [conteos_entrenamiento[c] + conteos_validacion[c] for c in categorias]
    balance = ("con el mismo número de ejemplos en cada categoría" if len(set(totales)) == 1
               else f"con entre {min(totales)} y {max(totales)} ejemplos por categoría")
    formato = ev["problema_de_formato_o_tono"]
    datos_txt = (f"con {n_total} ejemplos no se cumple el criterio de dataset grande ({MINIMO_EJEMPLOS_CURSO}); "
                 "sí alcanzan para ejemplos few-shot en el prompt y para un conjunto de control"
                 if n_total < MINIMO_EJEMPLOS_CURSO else
                 f"hay {n_total} ejemplos; el criterio de dataset grande depende además de la revisión manual")

    l: list[str] = [
        "# Decisión de personalización — Bloque 30",
        "",
        f"Generado con `python -m src.decision_personalizacion` (repositorio en {referencia_git}). "
        "No se llamó a la API de Gemini ni se creó ningún trabajo de tuning.",
        "",
        SECCIONES[0],
        "",
        "Queremos que el modelo convierta un mensaje de error técnico del proyecto en un JSON con exactamente dos "
        "claves, `categoria` y `accion_sugerida`, con categorías fijas "
        f"({', '.join(f'`{c}`' for c in categorias)}) y acciones coherentes con la política del código "
        "(`src/cliente.py`, `src/rag/reintentos.py`, `src/rag/errores.py`): los fallos de red y 5xx se reintentan "
        "con backoff exponencial, los 429 también pero requieren bajar el ritmo, y las credenciales nunca se reintentan.",
        "",
        "Es un problema de **consistencia de clasificación y formato**, no de conocimiento documental.",
        "",
        "**Evidencia disponible:**",
        "",
        f"- Dataset propio validado: {n_ent} ejemplos de entrenamiento y {n_val} de validación "
        f"({n_total} en total), sin errores de validación y {balance}.",
        f"- Muestra de respuestas reales del modelo base: {formato.detalle}",
        "- Por lo tanto, todavía **no está demostrado** que el modelo base falle en el formato: es la hipótesis que "
        "motiva el análisis." if formato.valor is None else
        f"- El criterio de formato {'se cumple' if formato.valor else 'no se cumple'} con esa muestra.",
        "",
        SECCIONES[1],
        "",
        "Cada criterio verdadero suma a cada estrategia el peso oficial del curso (tabla `PESOS` de "
        "`src/personalizacion/decision.py`). Un criterio no verificado no suma y **no se trata como «No»**.",
        "",
        "| Criterio | RAG | Fine-tuning completo | PEFT |",
        "|---|---:|---:|---:|",
        *[f"| `{c}` | " + " | ".join(str(PESOS[c].get(e, 0)) for e in ESTRATEGIAS) + " |" for c in CRITERIOS],
        "",
        "| Criterio | Umbral del curso | Hipótesis inicial | Valor comprobado | Estado | Cómo se comprobó |",
        "|---|---|---|---|---|---|",
    ]
    for nombre, descripcion in CRITERIOS.items():
        e = ev[nombre]
        l.append(f"| `{nombre}` | {descripcion} | {_si_no(HIPOTESIS_INICIAL[nombre])} | {_si_no(e.valor)} | "
                 f"{e.estado} | {e.detalle} |")
    l += [
        "",
        ("**Puntaje PROVISIONAL con los criterios comprobados** (hay criterios sin verificar; no es una decisión "
         "final plenamente fundamentada):" if resultado.provisional else
         "**Puntaje con todos los criterios comprobados:**"),
        "",
        *_tabla_puntos(resultado, con_maximo=resultado.provisional),
        "",
        _empate(resultado),
        "",
        *_lineas_escenarios(valores),
        *_lineas_sensibilidad(valores, ev),
        f"**Ejemplo oficial del curso** (formato Sí, dataset Sí, resto No; solo como referencia del método): "
        + ", ".join(f"{e} {ejemplo_oficial.puntos[e]}" for e in ESTRATEGIAS) + ". " + _empate(ejemplo_oficial),
        "",
        "**Con la hipótesis inicial (solo como contraste, no como evaluación final):**",
        "",
        *_tabla_puntos(resultado_hipotesis, con_maximo=False),
        "",
        _empate(resultado_hipotesis),
        "",
    ]
    diferencias = [c for c in CRITERIOS if HIPOTESIS_INICIAL[c] != ev[c].valor]
    if diferencias:
        l.append("La evidencia contradice o no confirma la hipótesis en: "
                 + ", ".join(f"`{c}` ({_si_no(HIPOTESIS_INICIAL[c])} → {_si_no(ev[c].valor)})" for c in diferencias) + ".")
        l.append("")

    l += [
        SECCIONES[2],
        "",
        f"**Implementación inmediata: {rec['inmediata']}.** **Evolución futura: {rec['futura']}.**",
        "",
        f"Motivo principal: {rec['motivo']}.",
        "",
        f"- **Datos:** {datos_txt}.",
        "- **Formato:** el contrato (`SalidaClasificacion` en `src/personalizacion/salida_estructurada.py`: "
        "categorías `Literal`, `extra=\"forbid\"`, acción no vacía) puede imponerse con salida estructurada "
        "(`response_mime_type=\"application/json\"` + `response_schema`) y validarse siempre en el cliente. "
        "Eso ataca directamente el síntoma sin entrenar.",
        f"- **Infraestructura:** {_texto_infraestructura(sdk, compatibilidad)}.",
        "- **Presupuesto:** no hay presupuesto de tuning documentado ni tarifas de entrenamiento en "
        "`data/tarifas_gemini.json`; Prompt + Pydantic solo consume las llamadas de inferencia que ya existen.",
        "- **Esfuerzo humano:** la línea base reutiliza los " + str(n_total) + " ejemplos actuales; el tuning exigiría "
        f"etiquetar y revisar al menos {faltan} más (ver sección 4).",
        "- **Conocimiento cambiante:** el catálogo de errores cambia con el código. Mantenerlo en el prompt (o "
        "recuperarlo) permite actualizarlo sin reentrenar; un adapter lo congelaría en el momento del entrenamiento.",
        "",
        "No se afirma que PEFT, fine-tuning o RAG sean mejores o peores que el prompt: no hay experimentos que lo midan.",
        "",
        SECCIONES[3],
        "",
        "| Elemento | Situación actual | Pendiente |",
        "|---|---|---|",
        f"| Ejemplos etiquetados | {n_total} ({n_ent} entrenamiento + {n_val} validación) | "
        f"{faltan} más para llegar a {MINIMO_EJEMPLOS_CURSO} (mínimo orientativo del curso, no de la API) |",
        f"| Cobertura por categoría | " + ", ".join(
            f"{c}: {conteos_entrenamiento[c] + conteos_validacion[c]}" for c in categorias) + " | "
        f"≈ {por_categoria_objetivo} por categoría para mantener el balance ({len(categorias)} categorías) |",
        f"| Revisión manual | No realizada | Revisar {REVISION_MANUAL} ejemplos con un criterio escrito |",
        f"| Tiempo de etiquetado | — | ≈ {minutos} min (≈ {f'{minutos / 60:.1f}'.replace('.', ',')} h). **Supuesto:** "
        f"{MINUTOS_POR_EJEMPLO_SUPUESTO} min por ejemplo nuevo y {MINUTOS_REVISION_SUPUESTO} min por ejemplo revisado; no medido |",
        f"| Muestra de formato del modelo base | No existe | {MUESTRA_FORMATO} respuestas reales guardadas en "
        f"`data/personalizacion/respuestas_modelo_base.json`; umbral {UMBRAL_INCUMPLIMIENTO:.0%} |",
        "| Línea base Prompt + Pydantic | Esquema y configuración construidos localmente | Medir su incumplimiento "
        "con la misma muestra antes de decidir tuning |",
    ]
    for etiqueta, compat in compatibilidad.items():
        if compat.get("verificable"):
            estado = "; ".join(f"{modo}: {'aceptada' if compat[modo] is None else 'rechazada'}"
                               for modo in ("gemini_developer_api", "vertex"))
        else:
            estado = f"no verificable ({compat.get('motivo')})"
        l.append(f"| SDK: {etiqueta} + PEFT | {estado} (conversores locales del SDK) | — |")
    l += [
        "| Requisitos técnicos | Clave de la API de Gemini (modo Developer API) | Para PEFT: proyecto de Google Cloud "
        "con Vertex, bucket de Cloud Storage, dataset en el formato JSONL que exija el servicio y cliente en modo Vertex |",
        "| Disponibilidad de tuning en modelo y cuenta | **No verificada** (no se consultó la API); "
        "`MODELOS_TUNING_VERIFICADOS` está vacío | Confirmar en la documentación oficial y en la cuenta qué modelo "
        "base admite tuning supervisado con adapters |",
        "| Presupuesto | **Pendiente de verificar**; no se presupone ningún costo | Obtener las tarifas oficiales de "
        "entrenamiento y del modelo ajustado, y aprobar un tope |",
        "| Autorización | `crear_trabajo_tuning` bloqueado por defecto | Autorización explícita, variable de entorno "
        "y modelo verificado (las tres condiciones) |",
        "",
    ]
    return "\n".join(l)
