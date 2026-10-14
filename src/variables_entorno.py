from dotenv import load_dotenv #Importando la función load_dotenv del módulo dotenv
import os #Importando el módulo os para acceder a las variables de entorno

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

print(os.getenv("API_KEY")) #Imprimiendo el valor de la variable de entorno API_KEY
print(os.getenv("AI_MODEL")) #Imprimiendo el valor de la variable de entorno AI_MODEL