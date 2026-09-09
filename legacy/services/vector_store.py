from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStore

from config.settings import settings
from services.embedder_model_manager import EmbedderModelManager


def create_vector_store(embedder: EmbedderModelManager | None = None) -> VectorStore:
    """Build a Chroma vector store backed by the configured persist directory.

    If *embedder* is not supplied one will be created and loaded automatically.
    """
    if embedder is None:
        embedder = EmbedderModelManager()
        embedder.load_model()

    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=embedder,
        persist_directory=settings.chroma_persist_dir,
    )
