"""Preflight de entrega del Gate 2: verifica el entorno sin llamar a Gemini.

Uso: python -m src.preflight_gate2
Código de salida 0 si no hay errores (puede haber advertencias). Reutiliza `src.rag.preflight`
(Bloque 28) y agrega dependencias, documentación, registro de prompts, matriz y búsqueda de secretos.
El índice real se abre solo en lectura; si no existe, el modo DEMO sigue disponible.
"""
from __future__ import annotations

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from src.rag.configuracion import CONFIG_BLOQUE26_MD, MODELO_EMBEDDINGS, RAIZ_REPO, obtener_modelo_chat
from src.rag.preflight import ADVERTENCIA, ERROR, OK, Resultado, comprobar_gitignore, comprobar_indice, \
    comprobar_tarifas

PYTHON_MINIMO = (3, 10)  # Igual que el README; la suite se verificó con 3.13.5.
DOCUMENTOS = ("README.md", "docs/README-gate2.md", "docs/ensayo-gate2.md", "docs/rubrica-gate2.md",
              "docs/entrega-gate2.md", "docs/resultados_evaluacion_bloque27.md", "docs/resultados_bloque28.md",
              "docs/decision_personalizacion.md", "docs/informe_seguridad_bloque31.md", "docs/matriz_riesgos_bloque32.md")
ARCHIVOS_SERVICIO = ("src/servicio_rag.py", "src/ensayo_gate2.py", "src/rubrica_gate2.py", "src/rag/auditoria.py",
                     "data/tarifas_gemini.json", "data/gobernanza/registro_prompts.json",
                     "data/gobernanza/matriz_riesgos.json", "data/gate2/autoevaluacion.json", ".env.example")
PATRONES_SECRETO = (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
                    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"))
EXTENSIONES_TEXTO = {".py", ".md", ".json", ".jsonl", ".txt", ".csv", ".toml", ".cfg", ".ini", ".yml", ".yaml", ""}


def comprobar_python() -> list[Resultado]:
    version = sys.version_info[:3]
    if version[:2] < PYTHON_MINIMO:
        return [Resultado(ERROR, "python", f"Python {'.'.join(map(str, version))} < 3.10.", "Instala Python 3.10 o superior.")]
    return [Resultado(OK, "python", f"Python {'.'.join(map(str, version))} (probado con 3.13.5).")]


def requisitos(raiz: Path = RAIZ_REPO) -> list[tuple[str, str | None]]:
    pares = []
    for linea in (raiz / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea:
            nombre, _, version = linea.partition("==")
            pares.append((re.split(r"[<>=!~]", nombre)[0].strip(), version.strip() or None))
    return pares


def comprobar_dependencias(raiz: Path = RAIZ_REPO) -> list[Resultado]:
    resultados = []
    for nombre, esperada in requisitos(raiz):
        try:
            instalada = metadata.version(nombre)
        except metadata.PackageNotFoundError:
            resultados.append(Resultado(ERROR, "dependencias", f"Falta {nombre}.", "python -m pip install -r requirements.txt"))
            continue
        if esperada and instalada != esperada:
            resultados.append(Resultado(ADVERTENCIA, "dependencias", f"{nombre} {instalada} (requirements fija {esperada}).",
                                        "python -m pip install -r requirements.txt"))
    if not resultados:
        resultados.append(Resultado(OK, "dependencias", f"{len(requisitos(raiz))} requisitos instalados con la versión fijada."))
    return resultados


def comprobar_archivos(raiz: Path, rutas: tuple[str, ...], etiqueta: str) -> list[Resultado]:
    faltan = [r for r in rutas if not (raiz / r).is_file()]
    if faltan:
        return [Resultado(ERROR, etiqueta, f"Faltan: {faltan}.", "Genera o restaura esos archivos.")]
    return [Resultado(OK, etiqueta, f"{len(rutas)} archivos presentes.")]


def comprobar_modelos() -> list[Resultado]:
    return [Resultado(OK, "modelos", f"Generación: {obtener_modelo_chat()} (AI_MODEL o predeterminado); "
                                     f"embeddings: {MODELO_EMBEDDINGS}. El modo DEMO usa modelos simulados y no requiere .env.")]


def comprobar_indice_real() -> list[Resultado]:
    """Lectura del índice real. Si falta, es advertencia: el modo DEMO crea su índice temporal."""
    resultados = comprobar_indice(CONFIG_BLOQUE26_MD)
    return [Resultado(ADVERTENCIA if r.nivel == ERROR else r.nivel, "índice real", r.mensaje,
                      (r.accion + " El modo DEMO no lo necesita.") if r.nivel == ERROR else r.accion) for r in resultados]


def comprobar_gobernanza() -> list[Resultado]:
    from src.gobernanza.matriz_riesgos import cargar_matriz, sin_supervision_requerida
    from src.gobernanza.registro_prompts import RUTA_REGISTRO, RegistroDePrompts, identificar_prompt_enviado
    from src.rag.seguridad_prompt import construir_prompt_seguro

    resultados = []
    try:
        registro = RegistroDePrompts(RUTA_REGISTRO)
        info = identificar_prompt_enviado(construir_prompt_seguro("¿?", "x").to_messages())
        nivel = OK if info["prompt_es_activa"] else ADVERTENCIA
        resultados.append(Resultado(nivel, "registro de prompts",
                                    f"{len(registro.listar())} versiones; el código envía v{info['prompt_version']} "
                                    f"({'activa' if info['prompt_es_activa'] else 'NO activa'})."))
    except Exception as error:  # noqa: BLE001 - se informa cualquier problema de carga
        resultados.append(Resultado(ERROR, "registro de prompts", f"{type(error).__name__}: {error}",
                                    "Restaura data/gobernanza/registro_prompts.json desde git."))
    try:
        riesgos = cargar_matriz()
        sin_control = sin_supervision_requerida(riesgos)
        resultados.append(Resultado(ERROR if sin_control else OK, "matriz de riesgos",
                                    f"{len(riesgos)} riesgos válidos; ALTO/CRITICO sin control: {sin_control or 'ninguno'}."))
    except Exception as error:  # noqa: BLE001
        resultados.append(Resultado(ERROR, "matriz de riesgos", f"{type(error).__name__}: {error}",
                                    "Corrige data/gobernanza/matriz_riesgos.json."))
    return resultados


def archivos_para_commit(raiz: Path = RAIZ_REPO) -> list[Path] | None:
    """Versionados + nuevos no ignorados (lo que `git add -A` incluiría)."""
    try:
        salida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=raiz,
                                capture_output=True, text=True, encoding="utf-8", timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [raiz / linea for linea in salida.splitlines() if linea.strip()]


def buscar_secretos(archivos: list[Path]) -> list[str]:
    hallazgos = []
    for ruta in archivos:
        if ruta.suffix.lower() not in EXTENSIONES_TEXTO or not ruta.is_file() or ruta.stat().st_size > 5_000_000:
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(texto) for p in PATRONES_SECRETO):
            hallazgos.append(str(ruta))
    return hallazgos


def comprobar_secretos(raiz: Path = RAIZ_REPO) -> list[Resultado]:
    archivos = archivos_para_commit(raiz)
    if archivos is None:
        return [Resultado(ADVERTENCIA, "secretos", "No se pudo listar archivos con git.", "Revisa manualmente.")]
    hallazgos = buscar_secretos(archivos)
    if hallazgos:  # Se informa la ruta, nunca el valor.
        return [Resultado(ERROR, "secretos", f"Posibles credenciales en: {hallazgos}.", "Quítalas antes del commit.")]
    return [Resultado(OK, "secretos", f"{len(archivos)} archivos destinados al commit revisados; sin credenciales.")]


def ejecutar(raiz: Path = RAIZ_REPO) -> list[Resultado]:
    return [*comprobar_python(), *comprobar_dependencias(raiz), *comprobar_gitignore(raiz),
            *comprobar_archivos(raiz, DOCUMENTOS, "documentación"), *comprobar_archivos(raiz, ARCHIVOS_SERVICIO, "servicio"),
            *comprobar_modelos(), *comprobar_tarifas(obtener_modelo_chat()),
            *comprobar_indice_real(), *comprobar_gobernanza(), *comprobar_secretos(raiz)]


def main() -> int:
    resultados = ejecutar()
    for r in resultados:
        print(f"[{r.nivel:<11}] {r.comprobacion}: {r.mensaje}" + (f"\n              → {r.accion}" if r.accion else ""))
    errores = sum(r.nivel == ERROR for r in resultados)
    print(f"\nResumen: {errores} errores, {sum(r.nivel == ADVERTENCIA for r in resultados)} advertencias. "
          "No se verificó la clave ni la cuota de Gemini (requeriría una llamada).")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
