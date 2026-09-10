from __future__ import annotations

from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import settings

_collection: Collection | None = None


def get_collection() -> Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _collection = client.get_or_create_collection(name=settings.chroma_collection)
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
