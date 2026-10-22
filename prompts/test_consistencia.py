"""Prueba al menos tres repeticiones por prompt contra Gemini.

Desde la raíz del repo:
    python -m prompts.test_consistencia
    python -m prompts.test_consistencia --repeticiones 5 --espera 3

Registra los intentos reales en prompts/registro_resultados.json.
"""
import argparse
import json
import os
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from prompts.banco import BANCO_DE_PROMPTS
from src.consumir_gemini import armar_peticion, enviar_peticion, extraer_texto

load_dotenv(RAIZ / ".env")
RESULTADOS = RAIZ / "prompts" / "registro_resultados.json"


def parsear_respuesta_json(texto: str) -> dict:
    """Interpreta el JSON, con soporte para cercos Markdown ocasionales."""
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("Respuesta vacía o no textual")
    limpio = texto.strip()
    if limpio.startswith("```"):
        lineas = limpio.splitlines()
        if len(lineas) < 3 or not lineas[-1].strip().startswith("```"):
            raise ValueError("Bloque de código no cerrado")
        limpio = "\n".join(lineas[1:-1]).strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido: {error.msg}") from error
    if not isinstance(datos, dict):
        raise ValueError("La raíz del JSON debe ser un objeto")
    return datos


def validar_estructura(datos: dict, prompt: dict) -> None:
    tipos = prompt["claves_esperadas"]
    if set(datos) != set(tipos):
        raise ValueError(f"Claves distintas: esperado {sorted(tipos)}; recibido {sorted(datos)}")
    for clave, tipo in tipos.items():
        valor = datos[clave]
        if tipo == "str" and (not isinstance(valor, str) or not valor.strip()):
            raise ValueError(f"{clave} debe ser texto no vacío")
        if tipo == "float" and (isinstance(valor, bool) or not isinstance(valor, (int, float))):
            raise ValueError(f"{clave} debe ser un número")
        if tipo == "list[str]" and (not isinstance(valor, list) or any(not isinstance(x, str) or not x.strip() for x in valor)):
            raise ValueError(f"{clave} debe ser lista de textos")
    if prompt["nombre"] == "clasificar_sentimiento":
        if datos["sentimiento"] not in ("positivo", "negativo", "neutro"):
            raise ValueError("Sentimiento fuera del conjunto permitido")
        if not 0 <= datos["confianza"] <= 1:
            raise ValueError("Confianza fuera de [0,1]")
    if prompt["nombre"] == "resumen_corto":
        if len(datos["resumen"]) > 240 or not 1 <= len(datos["ideas_clave"]) <= 3:
            raise ValueError("Longitud de resumen o cantidad de ideas fuera de rango")


def crear_peticion_estructurada(prompt: dict):
    """Reutiliza armar_peticion original sin modificar el módulo del curso."""
    url, encabezados, cuerpo = armar_peticion(prompt["ejemplo_usuario"])
    cuerpo["systemInstruction"] = {"parts": [{"text": prompt["system_instruction"]}]}
    cuerpo["generationConfig"] = {
        "responseMimeType": "application/json",
        "responseSchema": prompt["response_schema"],
        "temperature": 0,
    }
    return url, encabezados, cuerpo


def es_error_transitorio(exc: Exception) -> bool:
    """Distingue fallas de red/cuota de errores de JSON o validación.

    consumir_gemini.enviar_peticion() convierte los fallos HTTP y de conexión
    en RuntimeError; se inspecciona su causa cuando está disponible.
    """
    mensaje = str(exc).lower()
    if isinstance(exc, RuntimeError):
        if re.search(r"(?:error\s+)(429|500|502|503|504)\b", mensaje):
            return True
        if "no respondió" in mensaje or "revisa tu conexión" in mensaje:
            return True
    return False


def consultar_con_reintentos(url, encabezados, cuerpo, max_reintentos: int):
    """Devuelve (respuesta, reintentos_usados), preservando el error final.

    Cada repetición del experimento sigue siendo independiente. Un reintento
    solo rescata un fallo transitorio dentro de la misma repetición.
    """
    for reintento in range(max_reintentos + 1):
        try:
            return enviar_peticion(url, encabezados, cuerpo), reintento
        except RuntimeError as exc:
            if not es_error_transitorio(exc) or reintento == max_reintentos:
                raise
            pausa = min(2 ** (reintento + 1), 12)
            print(f"  error transitorio: {exc}; reintento {reintento + 1}/{max_reintentos} en {pausa}s")
            time.sleep(pausa)


def ejecutar(repeticiones: int, espera: float, max_reintentos: int = 2):
    if repeticiones < 3:
        raise ValueError("La actividad requiere al menos 3 repeticiones")
    if espera < 0:
        raise ValueError("La espera no puede ser negativa")
    if max_reintentos < 0:
        raise ValueError("max_reintentos no puede ser negativo")
    if not (os.getenv("API_KEY") and os.getenv("AI_MODEL")):
        raise RuntimeError("Configura API_KEY y AI_MODEL en el .env de la raíz")
    registro = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "modelo": os.environ["AI_MODEL"],
        "repeticiones_por_prompt": repeticiones,
        "max_reintentos_transitorios": max_reintentos,
        "prompts": {},
    }
    for prompt in BANCO_DE_PROMPTS:
        nombre = prompt["nombre"]
        intentos = []
        for n in range(1, repeticiones + 1):
            inicio = time.perf_counter()
            reintentos_usados = 0
            categoria_fallo = None
            try:
                url, encabezados, cuerpo = crear_peticion_estructurada(prompt)
                respuesta, reintentos_usados = consultar_con_reintentos(
                    url, encabezados, cuerpo, max_reintentos
                )
                texto = extraer_texto(respuesta)
                datos = parsear_respuesta_json(texto)
                validar_estructura(datos, prompt)
                estado, error = "exito", None
            except (ValueError, RuntimeError, KeyError, IndexError, TypeError) as exc:
                estado, error = "fallo", f"{type(exc).__name__}: {exc}"
                categoria_fallo = "servicio" if es_error_transitorio(exc) else (
                    "estructura_o_json" if isinstance(exc, ValueError) else "otro"
                )
            duracion = round(time.perf_counter() - inicio, 4)
            intentos.append({
                "intento": n, "estado": estado, "segundos": duracion,
                "error": error, "categoria_fallo": categoria_fallo,
                "reintentos_usados": reintentos_usados,
            })
            print(f"{nombre} intento {n}: {estado}" + (f" — {error}" if error else ""))
            if espera and (n < repeticiones or prompt is not BANCO_DE_PROMPTS[-1]):
                time.sleep(espera)
        exitos = sum(i["estado"] == "exito" for i in intentos)
        registro["prompts"][nombre] = {
            "exitos": exitos, "fallos": repeticiones - exitos,
            "fallos_servicio": sum(i["categoria_fallo"] == "servicio" for i in intentos),
            "fallos_estructura_o_json": sum(i["categoria_fallo"] == "estructura_o_json" for i in intentos),
            "intentos": repeticiones, "consistencia_porcentaje": round(100 * exitos / repeticiones, 2),
            "detalle": intentos,
        }
        print(f"{nombre}: {exitos}/{repeticiones} respuestas válidas")
        # Guardado incremental para conservar evidencia si se interrumpe el proceso.
        RESULTADOS.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Resultados reales guardados en {RESULTADOS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--espera", type=float, default=3.0)
    parser.add_argument("--reintentos", type=int, default=2)
    args = parser.parse_args()
    ejecutar(args.repeticiones, args.espera, args.reintentos)
