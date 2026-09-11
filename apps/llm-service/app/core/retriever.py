from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.embedding_provider import get_embedding_provider
from app.core.vector_store import query as vector_query


def retrieve(
    question: str, k: int | None = None, ruleset: str | None = None
) -> list[dict[str, Any]]:
    provider = get_embedding_provider()
    embedding = provider.embed([question])[0]
    return vector_query(embedding, k or settings.retrieval_k, ruleset=ruleset)
