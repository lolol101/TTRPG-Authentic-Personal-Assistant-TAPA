from app.core import retriever


class _FakeProvider:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[0.1, 0.2] for _ in texts]


def test_retrieve_embeds_question_and_queries_store(monkeypatch) -> None:
    fake_provider = _FakeProvider()
    monkeypatch.setattr(retriever, "get_embedding_provider", lambda: fake_provider)

    captured = {}

    def _fake_query(embedding, k, ruleset=None):
        captured["embedding"] = embedding
        captured["k"] = k
        return [{"id": "x", "text": "t", "metadata": {"title": "T"}, "distance": 0.0}]

    monkeypatch.setattr(retriever, "vector_query", _fake_query)

    results = retriever.retrieve("Что делает Удар?", k=3)

    assert fake_provider.embedded == ["Что делает Удар?"]
    assert captured["embedding"] == [0.1, 0.2]
    assert captured["k"] == 3
    assert results[0]["id"] == "x"


def test_retrieve_defaults_k_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(retriever, "get_embedding_provider", lambda: _FakeProvider())
    monkeypatch.setattr(retriever.settings, "retrieval_k", 7)

    captured_k = {}

    def _fake_query(embedding, k, ruleset=None):
        captured_k["k"] = k
        return []

    monkeypatch.setattr(retriever, "vector_query", _fake_query)

    retriever.retrieve("вопрос", k=None)

    assert captured_k["k"] == 7


def test_retrieve_scopes_the_search_to_one_ruleset(monkeypatch) -> None:
    """Without this, a D&D question could be answered out of the PF2e books."""
    captured = {}

    def _fake_query(embedding, k, ruleset=None):
        captured["ruleset"] = ruleset
        return []

    monkeypatch.setattr(retriever, "vector_query", _fake_query)
    monkeypatch.setattr(retriever, "get_embedding_provider", _FakeProvider)

    retriever.retrieve("вопрос", 3, ruleset="dnd5e")

    assert captured["ruleset"] == "dnd5e"
