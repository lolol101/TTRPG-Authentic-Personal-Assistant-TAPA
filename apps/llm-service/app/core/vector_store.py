from __future__ import annotations

from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import collection_name, settings
from app.core.embedding_provider import get_embedding_provider

_collection: Collection | None = None


def get_collection() -> Collection:
    """The collection matching the embedding model actually in use.

    Tying the name to the model means a fallback to a different embedding
    backend reads its own index rather than querying vectors from one model
    against an index built by another.
    """
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = client.get_or_create_collection(
            name=collection_name(get_embedding_provider().model_id)
        )
    return _collection


def upsert(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    get_collection().upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query(embedding: list[float], k: int) -> list[dict[str, Any]]:
    """Return up to *k* nearest documents as {id, text, metadata, distance}."""
    result = get_collection().query(query_embeddings=[embedding], n_results=k)

    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    return [
        {"id": ids[i], "text": documents[i], "metadata": metadatas[i], "distance": distances[i]}
        for i in range(len(ids))
    ]
