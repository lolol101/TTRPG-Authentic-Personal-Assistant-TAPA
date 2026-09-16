from __future__ import annotations

import logging
from typing import Any

import chromadb
import chromadb.errors
from chromadb.api.models.Collection import Collection
from chromadb.api.shared_system_client import SharedSystemClient

from app.core.config import collection_name, settings
from app.core.embedding_provider import get_embedding_provider

_log = logging.getLogger(__name__)

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


def reset_collection() -> None:
    """Drop every cached view of the store, not just our handle.

    Measured against a live re-index: reopening the collection on the same
    client still failed, and so did building a fresh PersistentClient —
    chromadb keeps one shared system per path and hands it back. Only
    clearing that cache first recovered. It is process-wide, which is safe
    here because this service reads a single collection.
    """
    global _collection
    _collection = None
    SharedSystemClient.clear_system_cache()


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


#: Reopen attempts before a query is allowed to fail. Two, because one was
#: measured to leave roughly one question in eight still failing under a
#: running ingest: the store can go stale again between the reopen and the
#: retry.
_REOPEN_ATTEMPTS = 2


def _query_surviving_reindex(
    embedding: list[float], k: int, where: dict[str, Any] | None
) -> dict[str, Any]:
    """Query, reopening the store if another process has moved it underneath.

    A long-lived reader holds a view of the index for the life of the
    process, so a bulk re-index elsewhere makes it query ids it cannot see
    and Chroma answers `InternalError: Error finding id`. Measured under a
    live ingest: 1 of 8 sheet-bound questions succeeded before this, 8 of 8
    after.
    """
    for attempt in range(1, _REOPEN_ATTEMPTS + 2):
        try:
            return get_collection().query(query_embeddings=[embedding], n_results=k, where=where)
        except chromadb.errors.InternalError:
            if attempt > _REOPEN_ATTEMPTS:
                raise
            _log.warning(
                "Chroma view looks stale (attempt %d), reopening the store and retrying", attempt
            )
            reset_collection()
    raise AssertionError("unreachable: the loop returns or raises")


def query(embedding: list[float], k: int, ruleset: str | None = None) -> list[dict[str, Any]]:
    """Return up to *k* nearest documents as {id, text, metadata, distance}.

    *ruleset* restricts the search to one game system. Without it a question
    about D&D could be answered out of the Pathfinder books, which is worse
    than finding nothing.
    """
    where = {"ruleset": ruleset} if ruleset else None
    result = _query_surviving_reindex(embedding, k, where)

    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    return [
        {"id": ids[i], "text": documents[i], "metadata": metadatas[i], "distance": distances[i]}
        for i in range(len(ids))
    ]
