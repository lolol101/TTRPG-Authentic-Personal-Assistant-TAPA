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


def test_retrieve_narrows_the_search_to_the_areas_categories(monkeypatch) -> None:
    """A build's area search must look only where that area can be answered.

    Measured on the live index: unfiltered, "fighter class features level 1"
    returned five archetype feats and not one class feature.
    """
    captured = {}

    def _fake_query(embedding, k, ruleset=None, categories=None):
        captured["categories"] = categories
        return [
            {"id": str(i), "text": "t", "metadata": {"title": "T"}, "distance": 0.1}
            for i in range(k)
        ]

    monkeypatch.setattr(retriever, "vector_query", _fake_query)
    monkeypatch.setattr(retriever, "get_embedding_provider", _FakeProvider)

    retriever.retrieve("fighter class features", 5, categories=("classes", "class-features"))

    assert captured["categories"] == ("classes", "class-features")


def test_a_short_filtered_search_is_topped_up_from_the_whole_index(monkeypatch) -> None:
    """A wrongly named area must not be able to mean "the rules say nothing".

    The section a model names is a guess; 29 chunks describe every class, so
    a filtered search can also just run out. Either way the model still gets
    k chunks, with the on-section ones in front.
    """
    calls: list[tuple | None] = []

    def _fake_query(embedding, k, ruleset=None, categories=None):
        calls.append(categories)
        if categories:
            return [{"id": "in-section", "text": "t", "metadata": {"title": "A"}, "distance": 0.1}]
        return [
            {"id": "in-section", "text": "t", "metadata": {"title": "A"}, "distance": 0.1},
            {"id": "topped-up", "text": "t", "metadata": {"title": "B"}, "distance": 0.4},
        ]

    monkeypatch.setattr(retriever, "vector_query", _fake_query)
    monkeypatch.setattr(retriever, "get_embedding_provider", _FakeProvider)

    hits = retriever.retrieve("rogue class", 2, categories=("classes",))

    # Filtered first, then the unfiltered pass — and the overlap is not
    # counted twice.
    assert calls == [("classes",), None]
    assert [hit["id"] for hit in hits] == ["in-section", "topped-up"]


def test_a_full_filtered_search_does_not_touch_the_whole_index(monkeypatch) -> None:
    calls: list[tuple | None] = []

    def _fake_query(embedding, k, ruleset=None, categories=None):
        calls.append(categories)
        return [
            {"id": str(i), "text": "t", "metadata": {"title": "T"}, "distance": 0.1}
            for i in range(k)
        ]

    monkeypatch.setattr(retriever, "vector_query", _fake_query)
    monkeypatch.setattr(retriever, "get_embedding_provider", _FakeProvider)

    retriever.retrieve("feats", 3, categories=("feats",))

    assert calls == [("feats",)]


def test_an_unfiltered_search_never_asks_for_categories(monkeypatch) -> None:
    """The ordinary question path must keep the single plain search it had."""
    calls: list[dict] = []

    def _fake_query(embedding, k, ruleset=None, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(retriever, "vector_query", _fake_query)
    monkeypatch.setattr(retriever, "get_embedding_provider", _FakeProvider)

    retriever.retrieve("Что делает Grapple?", 5)

    assert calls == [{}]


def _hit(distance: float, title: str = "T") -> dict:
    return {"id": title, "text": "t", "metadata": {"title": title}, "distance": distance}


def test_is_weak_on_empty_retrieval() -> None:
    """No chunks came back at all — the strongest case there is."""
    assert retriever.is_weak([]) is True


def test_is_weak_when_the_closest_hit_is_still_far(monkeypatch) -> None:
    monkeypatch.setattr(retriever.settings, "retrieval_weak_distance", 0.85)

    assert retriever.is_weak([_hit(0.9), _hit(1.1)]) is True


def test_not_weak_when_the_closest_hit_clears_the_threshold(monkeypatch) -> None:
    monkeypatch.setattr(retriever.settings, "retrieval_weak_distance", 0.85)

    assert retriever.is_weak([_hit(0.7), _hit(1.2)]) is False


def test_is_weak_looks_at_the_closest_hit_not_the_average(monkeypatch) -> None:
    """One confident match should not be drowned out by four weak ones."""
    monkeypatch.setattr(retriever.settings, "retrieval_weak_distance", 0.85)

    assert retriever.is_weak([_hit(0.6), _hit(1.0), _hit(1.1), _hit(1.2), _hit(1.3)]) is False


def test_is_weak_right_at_the_threshold_is_not_weak(monkeypatch) -> None:
    monkeypatch.setattr(retriever.settings, "retrieval_weak_distance", 0.85)

    assert retriever.is_weak([_hit(0.85)]) is False
