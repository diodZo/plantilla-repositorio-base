import os #Importando el módulo os para acceder a las variables de entorno

import requests #Importando la librería requests para enviar peticiones HTTP
from dotenv import load_dotenv #Importando la función load_dotenv del módulo dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()


def preguntar_a_gemini(pregunta):
    """Envía una pregunta a Gemini y devuelve el texto generado por el modelo."""
    api_key = os.getenv("API_KEY") #Credencial leída desde el .env
    modelo = os.getenv("AI_MODEL") #Nombre del modelo, por ejemplo gemini-3.8-flash

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    encabezados = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    cuerpo = {"contents": [{"parts": [{"text": pregunta}]}]}

    respuesta = requests.post(url, headers=encabezados, json=cuerpo, timeout=30)
    respuesta.raise_for_status() #Lanza un error si la API responde con un código 4xx o 5xx
    datos = respuesta.json() #Convierte la respuesta de JSON a un diccionario de Python

    # El texto generado está en candidates -> content -> parts
    return datos["candidates"][0]["content"]["parts"][0]["text"]


if __name__ == "__main__":
    # Quien usa la función es quien decide imprimir el resultado
    print(preguntar_a_gemini("Explica en una frase qué es una API."))
