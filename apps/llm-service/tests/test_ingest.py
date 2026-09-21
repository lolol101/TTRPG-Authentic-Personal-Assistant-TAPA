from app import ingest


class _FakeProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


def test_to_metadata_flattens_traits_and_defaults_missing_fields() -> None:
    record = {
        "url": "https://pf2.ru/actions/strike",
        "title": "Удар",
        "category": "actions",
        "source_book": "Основная книга игрока",
        "traits": ["Атака"],
        "language": "ru",
        "ruleset": "pf2e",
    }

    metadata = ingest.to_metadata(record)

    assert metadata == {
        "url": "https://pf2.ru/actions/strike",
        "title": "Удар",
        "category": "actions",
        "source_book": "Основная книга игрока",
        "traits": "Атака",
        "language": "ru",
        "ruleset": "pf2e",
    }


def test_to_metadata_handles_missing_source_book_and_traits() -> None:
    record = {
        "url": "https://pf2.ru/actions/x",
        "title": "X",
        "category": "actions",
        "source_book": None,
        "traits": [],
    }

    metadata = ingest.to_metadata(record)

    assert metadata["source_book"] == ""
    assert metadata["traits"] == ""
    assert metadata["language"] == "ru"


def test_ingest_records_upserts_in_batches(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(ingest, "upsert", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(ingest, "_BATCH_SIZE", 2)

    records = [
        {"id": str(i), "url": "u", "title": "t", "category": "actions", "text": "x" * i}
        for i in range(5)
    ]

    total = ingest.ingest_records(records, _FakeProvider())

    assert total == 5
    assert len(calls) == 3  # batches of 2, 2, 1
    assert calls[0]["ids"] == ["0", "1"]
    assert calls[-1]["ids"] == ["4"]


def test_load_records_skips_blank_lines(tmp_path) -> None:
    path = tmp_path / "chunks.jsonl"
    path.write_text('{"id": "a"}\n\n{"id": "b"}\n', encoding="utf-8")

    records = ingest.load_records(path)

    assert [r["id"] for r in records] == ["a", "b"]


def test_a_chunk_offered_twice_is_indexed_once(monkeypatch) -> None:
    """Chroma refuses a batch holding the same id twice, which failed the
    whole run. The crawl that produced those files is no longer repeatable,
    so the duplicates have to be tolerated here."""
    calls = []
    monkeypatch.setattr(ingest, "upsert", lambda **kwargs: calls.append(kwargs))

    records = [
        {"id": "a", "url": "u", "title": "t", "category": "actions", "text": "раз"},
        {"id": "b", "url": "u", "title": "t", "category": "actions", "text": "два"},
        {"id": "a", "url": "u", "title": "t", "category": "actions", "text": "раз"},
    ]

    total = ingest.ingest_records(records, _FakeProvider())

    assert total == 2
    assert calls[0]["ids"] == ["a", "b"]


def test_deduplication_does_not_split_a_full_batch(monkeypatch) -> None:
    """Dropping repeats after slicing would leave batches short of the size
    that was measured as safe for the embedding backend."""
    calls = []
    monkeypatch.setattr(ingest, "upsert", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(ingest, "_BATCH_SIZE", 2)

    records = [
        {"id": i, "url": "u", "title": "t", "category": "actions", "text": "x"}
        for i in ["a", "a", "b", "c"]
    ]

    ingest.ingest_records(records, _FakeProvider())

    assert [call["ids"] for call in calls] == [["a", "b"], ["c"]]


# --- resuming an interrupted build ---------------------------------------


def test_resume_skips_what_the_store_already_holds(monkeypatch) -> None:
    """A full build is hours of embedding calls; one timeout used to mean
    starting again from nothing. Ids hash the page url, so they are stable
    across runs and a second pass can tell done from outstanding."""
    records = [
        {"id": "a", "text": "первый", "url": "u1", "title": "A", "category": "feats"},
        {"id": "b", "text": "второй", "url": "u2", "title": "B", "category": "feats"},
        {"id": "c", "text": "третий", "url": "u3", "title": "C", "category": "feats"},
    ]

    monkeypatch.setattr(ingest, "already_indexed", lambda rows: {"a", "b"})

    embedded: list[str] = []
    stored: list[str] = []

    class _Provider:
        def embed(self, texts):
            embedded.extend(texts)
            return [[0.1] for _ in texts]

    monkeypatch.setattr(
        ingest, "upsert", lambda ids, embeddings, documents, metadatas: stored.extend(ids)
    )

    written = ingest.ingest_records(records, _Provider(), resume=True)

    assert written == 1
    assert embedded == ["третий"]
    assert stored == ["c"]


def test_without_resume_everything_is_embedded_again(monkeypatch) -> None:
    records = [
        {"id": "a", "text": "первый", "url": "u1", "title": "A", "category": "feats"},
        {"id": "b", "text": "второй", "url": "u2", "title": "B", "category": "feats"},
    ]

    called = {"checked": False}

    def _should_not_run(rows):
        called["checked"] = True
        return {"a"}

    monkeypatch.setattr(ingest, "already_indexed", _should_not_run)

    class _Provider:
        def embed(self, texts):
            return [[0.1] for _ in texts]

    monkeypatch.setattr(ingest, "upsert", lambda **kwargs: None)

    assert ingest.ingest_records(records, _Provider()) == 2
    assert called["checked"] is False


def test_resume_with_nothing_done_yet_writes_everything(monkeypatch) -> None:
    records = [{"id": "a", "text": "первый", "url": "u1", "title": "A", "category": "feats"}]
    monkeypatch.setattr(ingest, "already_indexed", lambda rows: set())

    class _Provider:
        def embed(self, texts):
            return [[0.1] for _ in texts]

    monkeypatch.setattr(ingest, "upsert", lambda **kwargs: None)

    assert ingest.ingest_records(records, _Provider(), resume=True) == 1


def test_already_indexed_asks_the_store_once_for_all_ids(monkeypatch) -> None:
    """Per-record lookups would trade the embedding calls we are saving for
    an equal number of store round trips."""
    asked: list[list[str]] = []

    class _Collection:
        def get(self, ids, include):
            asked.append(ids)
            return {"ids": ["a"]}

    monkeypatch.setattr(ingest, "get_collection", lambda: _Collection())

    records = [{"id": "a"}, {"id": "b"}]

    assert ingest.already_indexed(records) == {"a"}
    assert asked == [["a", "b"]]


def test_already_indexed_on_an_empty_batch_asks_nothing(monkeypatch) -> None:
    def _no_store():
        raise AssertionError("the store must not be opened for an empty batch")

    monkeypatch.setattr(ingest, "get_collection", _no_store)

    assert ingest.already_indexed([]) == set()
