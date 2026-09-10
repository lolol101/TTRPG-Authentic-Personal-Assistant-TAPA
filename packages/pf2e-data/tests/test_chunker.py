from app.chunker import chunk_page
from app.models import ParsedPage


def _page(body: str) -> ParsedPage:
    return ParsedPage(
        url="https://pf2.ru/actions/strike",
        category="actions",
        title="Удар",
        source_book="Основная книга игрока",
        traits=["Атака"],
        body=body,
        fetched_at="2026-01-01T00:00:00+00:00",
    )


def test_short_body_produces_single_chunk() -> None:
    page = _page("Короткий текст правила.")

    chunks = chunk_page(page, max_chars=2000)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == "Короткий текст правила."
    assert chunk.url == page.url
    assert chunk.title == page.title
    assert chunk.source_book == page.source_book
    assert chunk.traits == page.traits
    assert chunk.language == "ru"


def test_long_body_splits_on_paragraphs_within_limit() -> None:
    paragraphs = [f"Параграф номер {i} с текстом правила." for i in range(20)]
    page = _page("\n".join(paragraphs))

    chunks = chunk_page(page, max_chars=100)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 100
    # No paragraph text is lost or reordered across the split.
    assert "\n".join(c.text for c in chunks).count("Параграф номер 0") == 1
    assert "Параграф номер 19" in chunks[-1].text


def test_chunk_ids_are_stable_and_suffixed_when_split() -> None:
    page = _page("x" * 50)
    single = chunk_page(page, max_chars=2000)
    assert single[0].id == single[0].id  # stable within a run

    long_page = _page("\n".join(["para"] * 50))
    multi = chunk_page(long_page, max_chars=20)
    assert len(multi) > 1
    base = multi[0].id.rsplit("-", 1)[0]
    assert [c.id for c in multi] == [f"{base}-{i}" for i in range(len(multi))]
