import os #Importando el módulo os para acceder a las variables de entorno

import requests #Importando la librería requests para enviar peticiones HTTP
from dotenv import load_dotenv #Importando la función load_dotenv del módulo dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()


def armar_peticion(pregunta):
    """Arma la URL, los encabezados y el cuerpo de la petición a Gemini."""
    api_key = os.getenv("API_KEY") #Credencial leída desde el .env
    modelo = os.getenv("AI_MODEL") #Nombre del modelo, por ejemplo gemini-3.8-flash

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    encabezados = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    cuerpo = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, encabezados, cuerpo


def enviar_peticion(url, encabezados, cuerpo):
    """Envía la petición y devuelve la respuesta convertida a diccionario."""
    respuesta = requests.post(url, headers=encabezados, json=cuerpo, timeout=30)
    respuesta.raise_for_status() #Lanza un error si la API responde con un código 4xx o 5xx
    return respuesta.json() #Convierte la respuesta de JSON a un diccionario de Python


def extraer_texto(datos):
    """Recorre la respuesta de Gemini y devuelve el texto generado."""
    # El texto generado está en candidates -> content -> parts
    return datos["candidates"][0]["content"]["parts"][0]["text"]


def preguntar_a_gemini(pregunta):
    """Envía una pregunta a Gemini y devuelve el texto generado por el modelo."""
    url, encabezados, cuerpo = armar_peticion(pregunta)
    datos = enviar_peticion(url, encabezados, cuerpo)
    return extraer_texto(datos)


if __name__ == "__main__":
    # Quien usa la función es quien decide imprimir el resultado
    print(preguntar_a_gemini("Explica en una frase qué es una API."))
