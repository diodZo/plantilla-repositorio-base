"""Genera datos reales para los Bloques 16 y 17; no fabrica respuestas.

Desde raíz: python -m src.ensayo_bloque16 --cantidad 20
Cada petición exitosa se guarda de inmediato para permitir reanudar.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.cliente import consultar_modelo
from src.metricas_texto import calcular_metricas, resumir_metricas

RUTA = Path("docs/resultados_metricas.json")

# Referencias escritas previamente: su calidad también debe revisarse manualmente.
CASOS = [
    ("¿Qué es Python? Responde en una sola oración.", "Python es un lenguaje de programación interpretado de propósito general."),
    ("¿Qué es una lista en Python? Responde en una sola oración.", "Una lista en Python es una colección ordenada y modificable de elementos."),
    ("¿Qué es una tupla en Python? Responde en una sola oración.", "Una tupla es una colección ordenada e inmutable de elementos."),
    ("¿Qué es un diccionario de Python? Responde en una sola oración.", "Un diccionario guarda pares de clave y valor."),
    ("¿Qué es un set en Python? Responde en una sola oración.", "Un conjunto o set almacena elementos únicos sin un orden garantizado."),
    ("¿Para qué se usa una función en Python? Responde en una sola oración.", "Una función encapsula instrucciones reutilizables y puede recibir argumentos y devolver resultados."),
    ("¿Qué hace return en Python? Responde en una sola oración.", "La instrucción return termina una función y devuelve un valor al llamador."),
    ("¿Qué es un bucle for en Python? Responde en una sola oración.", "Un bucle for recorre elementos de un iterable."),
    ("¿Qué es un bucle while en Python? Responde en una sola oración.", "Un bucle while repite instrucciones mientras una condición sea verdadera."),
    ("¿Para qué sirve if en Python? Responde en una sola oración.", "La sentencia if ejecuta código cuando una condición es verdadera."),
    ("¿Qué hace len en Python? Responde en una sola oración.", "La función len devuelve la cantidad de elementos de un objeto compatible."),
    ("¿Qué hace print en Python? Responde en una sola oración.", "La función print muestra valores en la salida estándar."),
    ("¿Qué significa None en Python? Responde en una sola oración.", "None representa la ausencia de un valor."),
    ("¿Qué es una excepción en Python? Responde en una sola oración.", "Una excepción es un evento que interrumpe el flujo normal del programa."),
    ("¿Para qué sirve try except en Python? Responde en una sola oración.", "Try except permite capturar y manejar excepciones durante la ejecución."),
    ("¿Qué es un módulo de Python? Responde en una sola oración.", "Un módulo es un archivo de Python con definiciones e instrucciones reutilizables."),
    ("¿Qué es pip en Python? Responde en una sola oración.", "Pip es una herramienta para instalar y administrar paquetes de Python."),
    ("¿Para qué sirve un entorno virtual de Python? Responde en una sola oración.", "Un entorno virtual aísla las dependencias de un proyecto de Python."),
    ("¿Qué es JSON? Responde en una sola oración.", "JSON es un formato textual de intercambio de datos estructurados."),
    ("¿Qué es una API? Responde en una sola oración.", "Una API define mecanismos para que aplicaciones se comuniquen e intercambien datos."),
]


def cargar_resultados(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, list):
        raise ValueError("El JSON existente debe contener una lista.")
    if any(not isinstance(r, dict) or not {"consulta", "respuesta", "precision", "cobertura", "f1"} <= r.keys() for r in datos):
        raise ValueError("El JSON existente contiene registros incompletos.")
    return datos


def guardar_resultados(ruta: Path, resultados: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(resultados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporal.replace(ruta)


def ejecutar(cantidad: int, ruta: Path = RUTA) -> list[dict]:
    if not 1 <= cantidad <= len(CASOS):
        raise ValueError(f"La cantidad debe estar entre 1 y {len(CASOS)}.")
    resultados = cargar_resultados(ruta)
    existentes = {r["consulta"] for r in resultados}
    for n, (consulta, referencia) in enumerate(CASOS[:cantidad], start=1):
        if consulta in existentes:
            print(f"[{n}/{cantidad}] Ya registrado; se conserva la respuesta real.")
            continue
        print(f"[{n}/{cantidad}] Consultando Gemini: {consulta}")
        try:
            respuesta = consultar_modelo(consulta)
        except (ValueError, RuntimeError, TimeoutError) as error:
            print(f"Fallo en consulta {n}: {error}. Puedes reanudar con el mismo comando.")
            break
        if not isinstance(respuesta, str) or not respuesta.strip():
            print(f"Respuesta vacía en {n}; no se registra. Puedes reanudar.")
            break
        registro = {"consulta": consulta, "referencia": referencia, "respuesta": respuesta,
                    **calcular_metricas(referencia, respuesta),
                    "fecha_utc": datetime.now(timezone.utc).isoformat()}
        resultados.append(registro)
        existentes.add(consulta)
        guardar_resultados(ruta, resultados)
        print(f"   F1: {registro['f1']:.3f} | guardado: {ruta}")
    print(f"Registros en archivo: {len(resultados)}. Resumen: {resumir_metricas(resultados)}")
    return resultados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar métricas reales para Bloque 16 y 17")
    parser.add_argument("--cantidad", type=int, default=20, help="Número de consultas previstas (máximo 20)")
    parser.add_argument("--salida", type=Path, default=RUTA)
    argumentos = parser.parse_args()
    ejecutar(argumentos.cantidad, argumentos.salida)
