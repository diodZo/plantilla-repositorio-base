import os #Importando el módulo os para acceder a las variables de entorno

import requests #Importando la librería requests para enviar peticiones HTTP
from dotenv import load_dotenv #Importando la función load_dotenv del módulo dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()


def armar_peticion(pregunta):
    """Arma la URL, los encabezados y el cuerpo de la petición a Gemini."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    api_key = os.getenv("API_KEY") #Credencial leída desde el .env
    modelo = os.getenv("AI_MODEL") #Nombre del modelo, por ejemplo gemini-3.8-flash
    if not api_key or not modelo:
        raise ValueError("Faltan API_KEY o AI_MODEL en el archivo .env de la raíz del proyecto.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    encabezados = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    cuerpo = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, encabezados, cuerpo


def enviar_peticion(url, encabezados, cuerpo):
    """Envía la petición y devuelve la respuesta convertida a diccionario."""
    try:
        respuesta = requests.post(url, headers=encabezados, json=cuerpo, timeout=30)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
        raise RuntimeError("El servicio de Gemini no respondió. Revisa tu conexión e intenta de nuevo en unos segundos.") from error

    try:
        respuesta.raise_for_status() #Lanza un error si la API responde con un código 4xx o 5xx
    except requests.exceptions.HTTPError as error:
        raise RuntimeError(f"Gemini respondió con el error {respuesta.status_code}: {leer_mensaje_de_error(respuesta)}") from error

    try:
        return respuesta.json() #Convierte la respuesta de JSON a un diccionario de Python
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError("La respuesta de Gemini no llegó en formato JSON válido.") from error


def leer_mensaje_de_error(respuesta):
    """Devuelve el mensaje de error que envía Gemini, o el texto crudo si no viene en JSON."""
    try:
        return respuesta.json()["error"]["message"]
    except (requests.exceptions.JSONDecodeError, KeyError, TypeError):
        return respuesta.text[:200]


def extraer_texto(datos):
    """Recorre la respuesta de Gemini y devuelve el texto generado."""
    # El texto generado está en candidates -> content -> parts
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except KeyError as error:
        raise RuntimeError(f"La respuesta no trae el texto generado: falta el campo {error} en candidates -> content -> parts.") from error
    except IndexError as error:
        raise RuntimeError("La respuesta no trae el texto generado: la lista candidates o parts vino vacía.") from error


def preguntar_a_gemini(pregunta):
    """Envía una pregunta a Gemini y devuelve el texto generado por el modelo."""
    url, encabezados, cuerpo = armar_peticion(pregunta)
    datos = enviar_peticion(url, encabezados, cuerpo)
    return extraer_texto(datos)


if __name__ == "__main__":
    # Quien usa la función es quien decide imprimir el resultado y qué hacer con los errores
    try:
        print(preguntar_a_gemini("Explica en una frase qué es una API."))
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)
