"""Embeddings de Gemini con reintentos y contadores de uso."""
from __future__ import annotations

from langchain_core.embeddings import Embeddings

from src.rag.configuracion import MODELO_EMBEDDINGS, obtener_clave_api
from src.rag.errores import DependenciaFaltanteError
from src.rag.reintentos import llamar_con_reintentos


def crear_embeddings_gemini(modelo: str = MODELO_EMBEDDINGS, clave: str | None = None) -> Embeddings:
    """Embeddings reales. Lanza CredencialesFaltantesError antes de cualquier llamada si no hay clave."""
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError as error:
        raise DependenciaFaltanteError(
            "Falta langchain-google-genai. Ejecuta: python -m pip install -r requirements.txt"
        ) from error
    return GoogleGenerativeAIEmbeddings(model=modelo, google_api_key=clave or obtener_clave_api())


class EmbeddingsConReintentos(Embeddings):
    """Envoltorio: reintenta fallos transitorios y cuenta llamadas.

    Los contadores permiten comprobar que una consulta solo llama a
    `embed_query` y nunca a `embed_documents` (es decir, que no reindexa).
    """

    def __init__(self, base: Embeddings, intentos: int = 4, espera_base: float = 4, espera_maxima: float = 60):
        self.base = base
        self.intentos = intentos
        self.espera_base = espera_base
        self.espera_maxima = espera_maxima
        self.llamadas_documentos = 0
        self.textos_embebidos = 0
        self.llamadas_consulta = 0

    def _reintentar(self, funcion):
        return llamar_con_reintentos(funcion, self.intentos, self.espera_base, self.espera_maxima)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.llamadas_documentos += 1
        self.textos_embebidos += len(texts)
        return self._reintentar(lambda: self.base.embed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        self.llamadas_consulta += 1
        return self._reintentar(lambda: self.base.embed_query(text))
