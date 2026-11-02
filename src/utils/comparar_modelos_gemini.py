"""Benchmark reproducible de modelos Gemini. No modifica tu proyecto original."""
import csv
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Precios oficiales del nivel Standard de pago en USD / 1M tokens,
# de referencia; verificar precios e identificadores en la documentación oficial antes de interpretar los resultados.
MODELOS = {
    "gemini-3.5-flash-lite": {"entrada": 0.30, "salida": 2.50},
    "gemini-3.8-flash": {"entrada": 0.75, "salida": 3.75},
}
PREGUNTAS = [
    "¿Cuánto es 2 + 2? Responde solo con el resultado.",
    "¿Cuál es la capital de Escocia? Responde solo con el nombre.",
    "En una oración explica qué es una API REST.",
]
CICLOS = 5  # 5 rondas * 3 preguntas * 2 modelos = 30 solicitudes
DESTINO = ROOT / "docs" / "comparacion_modelos.csv"


def medir(modelo: str, pregunta: str, sesion: requests.Session) -> dict:
    clave = os.getenv("API_KEY")
    if not clave:
        raise RuntimeError("Falta API_KEY en el archivo .env de la raíz del proyecto")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {"contents": [{"parts": [{"text": pregunta}]}]}
    encabezados = {"x-goog-api-key": clave, "Content-Type": "application/json"}
    inicio = time.perf_counter()
    respuesta = sesion.post(url, json=payload, headers=encabezados, timeout=60)
    latencia = time.perf_counter() - inicio
    respuesta.raise_for_status()
    datos = respuesta.json()
    metadatos = datos.get("usageMetadata", {})
    entrada = metadatos.get("promptTokenCount", 0)
    salida_visible = metadatos.get("candidatesTokenCount", 0)
    razonamiento = metadatos.get("thoughtsTokenCount", 0)
    salida_facturable = salida_visible + razonamiento
    tarifas = MODELOS[modelo]
    costo = (entrada * tarifas["entrada"] + salida_facturable * tarifas["salida"]) / 1_000_000
    texto = ""
    try:
        texto = datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        pass
    return {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "modelo": modelo,
        "pregunta": pregunta,
        "latencia_segundos": round(latencia, 4),
        "tokens_entrada": entrada,
        "tokens_salida_visibles": salida_visible,
        "tokens_razonamiento": razonamiento,
        "tokens_totales_api": metadatos.get("totalTokenCount", ""),
        "costo_estimado_usd": round(costo, 9),
        "respuesta": texto.replace("\n", " ")[:250],
        "estado": "ok" if texto else "sin_texto",
    }


def ejecutar() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    resultados = []
    with requests.Session() as sesion:
        for ciclo in range(CICLOS):
            # Alternar el orden evita favorecer siempre al mismo modelo.
            orden = list(MODELOS)
            if ciclo % 2:
                orden.reverse()
            for pregunta in PREGUNTAS:
                for modelo in orden:
                    try:
                        fila = medir(modelo, pregunta, sesion)
                        print(f"[OK] {modelo}: {fila['latencia_segundos']:.3f}s; "
                              f"USD {fila['costo_estimado_usd']:.9f}")
                        resultados.append(fila)
                    except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
                        print(f"[ERROR] {modelo}: {type(exc).__name__}: {exc}")
                        resultados.append({
                            "fecha_utc": datetime.now(timezone.utc).isoformat(),
                            "modelo": modelo,
                            "pregunta": pregunta,
                            "latencia_segundos": "",
                            "tokens_entrada": "",
                            "tokens_salida_visibles": "",
                            "tokens_razonamiento": "",
                            "tokens_totales_api": "",
                            "costo_estimado_usd": "",
                            "respuesta": "",
                            "estado": f"error: {type(exc).__name__}",
                        })
                    time.sleep(0.5)

    with DESTINO.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=[
            "fecha_utc", "modelo", "pregunta", "latencia_segundos",
            "tokens_entrada", "tokens_salida_visibles", "tokens_razonamiento",
            "tokens_totales_api", "costo_estimado_usd", "respuesta", "estado"
        ])
        escritor.writeheader()
        escritor.writerows(resultados)

    print(f"\nResultados guardados en {DESTINO}")
    for modelo in MODELOS:
        correctos = [r for r in resultados if r["modelo"] == modelo and r["estado"] == "ok"]
        if not correctos:
            print(f"{modelo}: ninguna solicitud exitosa")
            continue
        latencias = [r["latencia_segundos"] for r in correctos]
        print(f"{modelo}: n={len(correctos)}, "
              f"media={statistics.mean(latencias):.3f}s, "
              f"mediana={statistics.median(latencias):.3f}s, "
              f"costo_total_estimado=USD {sum(r['costo_estimado_usd'] for r in correctos):.8f}")


if __name__ == "__main__":
    ejecutar()
