"""Excepciones del sistema RAG (Bloques 24–26).

Cada clase representa un fallo operativo identificable. Los errores de
programación (TypeError, AttributeError, etc.) no se envuelven en estas clases.
"""


class ErrorRAG(Exception):
    """Base de los errores operativos del RAG."""


class CredencialesFaltantesError(ErrorRAG):
    """No hay ninguna clave de Gemini configurada."""


class CredencialesInvalidasError(ErrorRAG):
    """La API rechazó la clave (400 API_KEY_INVALID, 401 o 403). No se reintenta."""


class ErrorTransitorio(ErrorRAG, TimeoutError):
    """Fallo recuperable (429, 5xx, red). Hereda de TimeoutError para reutilizar
    `src.cliente.con_reintento`, que solo reintenta ese tipo."""


class DependenciaFaltanteError(ErrorRAG):
    """Falta un paquete necesario (chromadb, langchain-chroma, langchain-google-genai)."""


class DirectorioNoEscribibleError(ErrorRAG):
    """No se puede crear o escribir el directorio del índice."""


class ColeccionInexistenteError(ErrorRAG):
    """Se intentó cargar un índice que no existe."""


class IndiceVacioError(ErrorRAG):
    """La colección existe, pero no tiene fragmentos."""


class EmbeddingsIncompatiblesError(ErrorRAG):
    """El modelo o la dimensión de embeddings no coincide con el índice."""


class ConfiguracionIncompatibleError(ErrorRAG):
    """La configuración de chunking no coincide con la del índice persistido."""


class MetadataFaltanteError(ErrorRAG):
    """Un documento o fragmento carece de la metadata de origen obligatoria."""


class DocumentoDuplicadoError(ErrorRAG):
    """Dos documentos o fragmentos comparten ruta, contenido o ID."""


class CorpusInvalidoError(ErrorRAG):
    """El corpus no existe, está vacío o no cumple el mínimo requerido."""
