import pytest

from app.core import vector_store


@pytest.fixture(autouse=True)
def _isolated_chroma(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store.settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(vector_store.settings, "chroma_collection", "test_collection")
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
