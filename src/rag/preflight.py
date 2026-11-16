"""Preflight del sistema RAG (Bloque 28): diagnóstico local SIN llamar a Gemini.

Uso:  python -m src.rag.preflight
Código de salida: 0 si no hay errores (puede haber advertencias); 1 si hay errores.

NO verifica que la clave de API sea válida ni que haya cuota: eso requiere una llamada externa.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.rag.configuracion import CONFIG_BLOQUE26_MD, MODELO_EMBEDDINGS, RAIZ_REPO, VARIABLES_CLAVE, ConfiguracionIndice
from src.rag.costos import ARCHIVO_TARIFAS, buscar_tarifa, cargar_tarifas

OK, ADVERTENCIA, ERROR = "OK", "ADVERTENCIA", "ERROR"
EXCLUSIONES_OBLIGATORIAS = (".env", ".venv/", "vectorstore/")
GENERADOS_PELIGROSOS = (r"(^|/)\.env$", r"^vectorstore(_ejemplo)?/", r"^\.venv/",
                        r"(^|/)registros_latencia_costo\.jsonl$", r"(^|/)trazas_agente_bloque23\.jsonl$")


@dataclass(frozen=True)
class Resultado:
    nivel: str
    comprobacion: str
    mensaje: str
    accion: str = ""


def _git(args: list[str], raiz: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def comprobar_gitignore(raiz: Path) -> list[Resultado]:
    ruta = raiz / ".gitignore"
    if not ruta.is_file():
        return [Resultado(ERROR, ".gitignore", "No existe .gitignore.",
                          "Créalo con al menos: .env, .venv/ y vectorstore/.")]
    lineas = [l.strip() for l in ruta.read_text(encoding="utf-8").splitlines()]
    resultados = []
    for patron in EXCLUSIONES_OBLIGATORIAS:
        presente = patron in lineas or patron.rstrip("/") in lineas
        efectivo = None
        proceso = _git(["check-ignore", "-q", patron.rstrip("/")], raiz)
        if proceso is not None and proceso.returncode in (0, 1):
            efectivo = proceso.returncode == 0
        if presente or efectivo:
            resultados.append(Resultado(OK, ".gitignore", f"{patron} está excluido."))
        else:
            resultados.append(Resultado(ERROR, ".gitignore", f"{patron} no está excluido.", f"Agrega '{patron}' a .gitignore."))
    for generado in ("registros_latencia_costo.jsonl", "trazas_agente_bloque23.jsonl"):
        proceso = _git(["check-ignore", "-q", generado], raiz)
        if proceso is not None and proceso.returncode == 1:
            resultados.append(Resultado(ADVERTENCIA, ".gitignore", f"{generado} (registro generado) no está excluido.",
                                        f"Agrega '{generado}' a .gitignore."))
    sospechosas = [l for l in lineas if l and not l.startswith("#") and " --" in l]
    for linea in sospechosas:
        resultados.append(Resultado(ADVERTENCIA, ".gitignore", f"Línea que parece un comando pegado por error: {linea!r}",
                                    "Revísala y elimínala si no es un patrón intencional."))
    return resultados


def comprobar_staging(raiz: Path) -> list[Resultado]:
    proceso = _git(["diff", "--cached", "--name-only"], raiz)
    if proceso is None or proceso.returncode != 0:
        return [Resultado(ADVERTENCIA, "staging", "No se pudo consultar el área de staging de Git.",
                          "Comprueba manualmente: git diff --cached --name-only")]
    preparados = [l.strip() for l in proceso.stdout.splitlines() if l.strip()]
    peligrosos = [p for p in preparados if any(re.search(r, p) for r in GENERADOS_PELIGROSOS)]
    if peligrosos:
        return [Resultado(ERROR, "staging", f"Archivos generados o secretos en staging: {peligrosos}",
                          "Quítalos con: git restore --staged <archivo>")]
    return [Resultado(OK, "staging", f"{len(preparados)} archivos en staging; ninguno es secreto ni generado.")]


def comprobar_credenciales(raiz: Path) -> list[Resultado]:
    """Solo comprueba que exista una variable configurada; no lee ni muestra su valor fuera de este proceso."""
    from dotenv import dotenv_values
    valores = dotenv_values(raiz / ".env") if (raiz / ".env").is_file() else {}
    configurada = any((valores.get(v) or os.getenv(v) or "").strip() not in ("", "coloca_aqui_tu_clave_real")
                      for v in VARIABLES_CLAVE)
    if not configurada:
        return [Resultado(ERROR, "credenciales", "No hay clave de Gemini configurada.",
                          f"Define {' o '.join(VARIABLES_CLAVE)} en .env (copia .env.example).")]
    return [Resultado(OK, "credenciales", "Hay una clave configurada (no se verifica su validez ni su cuota: requiere una llamada externa).")]


def comprobar_indice(config: ConfiguracionIndice) -> list[Resultado]:
    directorio = Path(config.directorio)
    if not directorio.is_dir():
        return [Resultado(ERROR, "índice", f"No existe {directorio}.",
                          "Indexa con: python -m src.indexar_corpus --bloque 24 --estrategia markdown "
                          f"--coleccion {config.nombre_coleccion}")]
    try:
        import chromadb
    except ImportError:
        return [Resultado(ERROR, "índice", "chromadb no está instalado.", "python -m pip install -r requirements.txt")]
    cliente = chromadb.PersistentClient(path=str(directorio))
    nombres = [c if isinstance(c, str) else c.name for c in cliente.list_collections()]
    if config.nombre_coleccion not in nombres:
        return [Resultado(ERROR, "índice", f"La colección {config.nombre_coleccion!r} no existe (hay: {nombres}).",
                          "Indexa la colección configurada; el preflight no la crea.")]
    coleccion = cliente.get_collection(config.nombre_coleccion)
    meta = coleccion.metadata or {}
    resultados = []
    n = coleccion.count()
    if n == 0:
        resultados.append(Resultado(ERROR, "índice", "La colección está vacía.", "Vuelve a indexar el corpus."))
    datos = coleccion.get(include=["metadatas"])
    sin_fuente = sum(1 for m in datos["metadatas"] if not m or not m.get("fuente"))
    documentos = len({m.get("fuente") for m in datos["metadatas"] if m and m.get("fuente")})
    resultados.append(Resultado(OK if n else ERROR, "índice",
                                f"{config.nombre_coleccion}: {n} chunks de {documentos} documentos "
                                f"({meta.get('estrategia')} {meta.get('chunk_size')}/{meta.get('chunk_overlap')})."))
    resultados.append(Resultado(ERROR if sin_fuente else OK, "metadatos",
                                f"{sin_fuente} chunks sin metadato 'fuente'." if sin_fuente else "Todos los chunks tienen 'fuente'.",
                                "Reindexa con metadatos de origen." if sin_fuente else ""))
    if meta.get("modelo_embeddings") != config.modelo_embeddings:
        resultados.append(Resultado(ERROR, "embeddings",
                                    f"La colección usa {meta.get('modelo_embeddings')!r} y la configuración {config.modelo_embeddings!r}.",
                                    "Usa el mismo modelo o reconstruye la colección de forma explícita."))
    else:
        resultados.append(Resultado(OK, "embeddings", f"Modelo de embeddings coherente: {config.modelo_embeddings}."))
    return resultados


def comprobar_evaluacion(raiz: Path) -> list[Resultado]:
    from src.rag.evaluacion_bloque27 import DatasetInvalidoError, cargar_dataset
    ruta = raiz / "data" / "evaluacion" / "bloque27_casos.json"
    if not ruta.is_file():
        return [Resultado(ADVERTENCIA, "evaluación", f"No existe {ruta.relative_to(raiz)}.", "Crea y congela el dataset del Bloque 27.")]
    try:
        datos = cargar_dataset(ruta)
    except DatasetInvalidoError as error:
        return [Resultado(ERROR, "evaluación", f"Dataset inválido: {error}", "Revisa data/evaluacion/bloque27_casos.json.")]
    return [Resultado(OK, "evaluación", f"Dataset del Bloque 27 válido y congelado ({len(datos['casos'])} casos).")]


def comprobar_tarifas(modelo_generacion: str) -> list[Resultado]:
    if not ARCHIVO_TARIFAS.is_file():
        return [Resultado(ADVERTENCIA, "tarifas", "No hay archivo de tarifas: los costos quedarán como desconocidos.",
                          f"Crea {ARCHIVO_TARIFAS.relative_to(RAIZ_REPO)}.")]
    try:
        tarifas = cargar_tarifas()
    except (ValueError, KeyError) as error:
        return [Resultado(ERROR, "tarifas", f"Archivo de tarifas inválido: {error}", "Corrige data/tarifas_gemini.json.")]
    resultados = []
    for modelo in (modelo_generacion, MODELO_EMBEDDINGS):
        tarifa = buscar_tarifa(tarifas, modelo)
        if tarifa is None:
            resultados.append(Resultado(ADVERTENCIA, "tarifas", f"Sin tarifa para {modelo}: su costo será desconocido.",
                                        "Agrega la tarifa con su fuente y fecha de consulta."))
        else:
            resultados.append(Resultado(OK, "tarifas", f"{modelo}: tarifa {tarifa.tipo} (consultada {tarifa.fecha_consulta})."))
    return resultados


def ejecutar_preflight(raiz: Path = RAIZ_REPO, config: ConfiguracionIndice = CONFIG_BLOQUE26_MD,
                       modelo_generacion: str | None = None) -> list[Resultado]:
    from src.rag.configuracion import obtener_modelo_chat
    modelo = modelo_generacion or obtener_modelo_chat()
    return [
        *comprobar_gitignore(raiz),
        *comprobar_staging(raiz),
        *comprobar_credenciales(raiz),
        *comprobar_indice(config),
        Resultado(OK, "modelo", f"Modelo de generación configurado: {modelo}."),
        *comprobar_tarifas(modelo),
        *comprobar_evaluacion(raiz),
    ]


def main() -> int:
    resultados = ejecutar_preflight()
    for r in resultados:
        print(f"[{r.nivel:<11}] {r.comprobacion}: {r.mensaje}" + (f"\n              → {r.accion}" if r.accion else ""))
    errores = sum(r.nivel == ERROR for r in resultados)
    advertencias = sum(r.nivel == ADVERTENCIA for r in resultados)
    print(f"\nResumen: {errores} errores, {advertencias} advertencias. "
          "No se verificó la validez de la clave ni la cuota (requiere llamar a Gemini).")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
