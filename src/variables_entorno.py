"""Comprueba que las variables de entorno estén configuradas, sin revelar secretos."""
import os
from pathlib import Path
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / '.env')

if __name__ == '__main__':
    print('API_KEY configurada:', bool(os.getenv('API_KEY')))
    print('AI_MODEL:', os.getenv('AI_MODEL') or '(sin configurar)')
