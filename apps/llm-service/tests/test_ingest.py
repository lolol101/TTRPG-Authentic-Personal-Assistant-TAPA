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
