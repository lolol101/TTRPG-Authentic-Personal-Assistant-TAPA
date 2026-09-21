import chromadb.errors
import pytest

from app.core import vector_store
from app.core.embedding_provider import EmbeddingProvider


class _StubProvider(EmbeddingProvider):
    """The collection name is derived from the model, so tests need one."""

    @property
    def model_id(self) -> str:
        return "test-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def _isolated_chroma(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(vector_store, "get_embedding_provider", lambda: _StubProvider())
    monkeypatch.setattr(vector_store, "_collection", None)
    yield
    monkeypatch.setattr(vector_store, "_collection", None)


def test_upsert_and_query_roundtrip() -> None:
    vector_store.upsert(
        ids=["a", "b"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        documents=["doc a", "doc b"],
        metadatas=[{"title": "A"}, {"title": "B"}],
    )

    results = vector_store.query([1.0, 0.0], k=1)

    assert len(results) == 1
    assert results[0]["id"] == "a"
    assert results[0]["text"] == "doc a"
    assert results[0]["metadata"]["title"] == "A"


def test_query_respects_k() -> None:
    vector_store.upsert(
        ids=["a", "b", "c"],
        embeddings=[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
        documents=["doc a", "doc b", "doc c"],
        metadatas=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
    )

    results = vector_store.query([1.0, 0.0], k=2)

    assert len(results) == 2
    assert {r["id"] for r in results} == {"a", "b"}


def test_a_stale_collection_handle_is_reopened_instead_of_failing() -> None:
    """A long-lived service holds its collection handle for the life of the
    process, and another process re-indexing underneath it makes that handle
    stale: Chroma then answers filtered queries with "Error finding id".

    Measured, not hypothesised: during a bulk re-index every sheet-bound
    question returned 500, while the same query from a fresh process worked
    20 times out of 20, and a restarted service worked twice before failing
    again. Retrying once on a fresh handle is what makes a re-index survivable.
    """
    vector_store.upsert(
        ids=["a"],
        embeddings=[[1.0, 0.0]],
        documents=["doc a"],
        metadatas=[{"title": "A"}],
    )
    live = vector_store.get_collection()
    calls = {"n": 0}
    real_query = live.query

    def _stale_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise chromadb.errors.InternalError(
                "Error executing plan: Internal error: Error finding id"
            )
        return real_query(*args, **kwargs)

    live.query = _stale_once  # type: ignore[method-assign]

    results = vector_store.query([1.0, 0.0], k=1)

    assert calls["n"] == 1, "the retry must go through a freshly opened handle"
    assert results[0]["id"] == "a"


def test_it_survives_going_stale_twice_in_a_row() -> None:
    """One reopen left about one question in eight still failing under a
    live ingest — the store can go stale again between the reopen and the
    retry."""
    vector_store.upsert(
        ids=["a"], embeddings=[[1.0, 0.0]], documents=["doc a"], metadatas=[{"title": "A"}]
    )
    calls = {"n": 0}
    real_query = vector_store.get_collection().query

    def _stale_twice(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise chromadb.errors.InternalError("Error finding id")
        return real_query(*args, **kwargs)

    def _patched_get_collection():
        collection = _real_get_collection()
        collection.query = _stale_twice  # type: ignore[method-assign]
        return collection

    _real_get_collection = vector_store.get_collection
    vector_store.get_collection = _patched_get_collection  # type: ignore[assignment]
    try:
        results = vector_store.query([1.0, 0.0], k=1)
    finally:
        vector_store.get_collection = _real_get_collection  # type: ignore[assignment]

    assert calls["n"] == 3
    assert results[0]["id"] == "a"


def test_an_unrelated_chroma_error_is_not_swallowed() -> None:
    """Retrying every failure would turn a real fault into a silent empty
    answer, which reads to a player as "the rules do not say"."""
    vector_store.upsert(
        ids=["a"], embeddings=[[1.0, 0.0]], documents=["doc a"], metadatas=[{"title": "A"}]
    )
    live = vector_store.get_collection()

    def _always_broken(*args, **kwargs):
        raise ValueError("collection schema mismatch")

    live.query = _always_broken  # type: ignore[method-assign]

    with pytest.raises(ValueError):
        vector_store.query([1.0, 0.0], k=1)


def test_upsert_overwrites_existing_id() -> None:
    vector_store.upsert(
        ids=["a"],
        embeddings=[[1.0, 0.0]],
        documents=["old"],
        metadatas=[{"title": "old"}],
    )
    vector_store.upsert(
        ids=["a"],
        embeddings=[[1.0, 0.0]],
        documents=["new"],
        metadatas=[{"title": "new"}],
    )

    results = vector_store.query([1.0, 0.0], k=5)

    assert len(results) == 1
    assert results[0]["text"] == "new"


def test_where_clause_is_none_when_nothing_is_restricted() -> None:
    assert vector_store.where_clause(None, None) is None


def test_where_clause_filters_on_one_ruleset() -> None:
    assert vector_store.where_clause("pf2e", None) == {"ruleset": {"$eq": "pf2e"}}


def test_where_clause_uses_eq_for_a_single_category() -> None:
    """Not $in with one operand: the clause reads as what it means."""
    assert vector_store.where_clause(None, ("backgrounds",)) == {"category": {"$eq": "backgrounds"}}


def test_where_clause_uses_in_for_several_categories() -> None:
    assert vector_store.where_clause(None, ("classes", "class-features")) == {
        "category": {"$in": ["classes", "class-features"]}
    }


def test_where_clause_combines_ruleset_and_categories_with_and() -> None:
    """Chroma rejects $and with a single operand, so it appears only here."""
    assert vector_store.where_clause("pf2e", ("feats",)) == {
        "$and": [{"ruleset": {"$eq": "pf2e"}}, {"category": {"$eq": "feats"}}]
    }


def test_an_empty_category_list_restricts_nothing() -> None:
    """sheet_plan returns None for an unmapped area, but a caller passing an
    empty tuple must not produce a clause that matches no chunk at all —
    Chroma answers a filter nothing satisfies with zero hits, not an error."""
    assert vector_store.where_clause(None, ()) is None
    assert vector_store.where_clause("pf2e", ()) == {"ruleset": {"$eq": "pf2e"}}


def test_a_category_filter_actually_narrows_a_real_query() -> None:
    """The clause is only useful if Chroma honours it — see the note on
    where_clause: a malformed filter looks exactly like an empty corpus."""
    vector_store.upsert(
        ids=["c1", "c2"],
        embeddings=[[1.0, 0.0], [0.9, 0.1]],
        documents=["Fighter class entry", "Basic Maneuver feat"],
        metadatas=[
            {"category": "classes", "ruleset": "pf2e", "title": "Fighter", "url": "u1"},
            {"category": "feats", "ruleset": "pf2e", "title": "Basic Maneuver", "url": "u2"},
        ],
    )

    everything = vector_store.query([1.0, 0.0], k=5, ruleset="pf2e")
    classes_only = vector_store.query([1.0, 0.0], k=5, ruleset="pf2e", categories=("classes",))

    assert {hit["id"] for hit in everything} == {"c1", "c2"}
    assert [hit["id"] for hit in classes_only] == ["c1"]
