from dataclasses import asdict

from app.core import corpus_language
from app.core.config import settings


def test_the_wording_follows_the_configured_corpus(monkeypatch) -> None:
    monkeypatch.setattr(settings, "corpus_language", "ru")
    assert corpus_language.wording().rewrite_tool == "search_the_rulebooks"

    monkeypatch.setattr(settings, "corpus_language", "en")
    assert corpus_language.wording().rewrite_tool == "search_the_rulebooks_in_english"


def test_a_russian_corpus_is_never_described_as_english_books() -> None:
    """The prompt used to state the books are English as a fact. Served over
    the Russian index, that sends every search query into the wrong language."""
    russian = corpus_language._RUSSIAN
    about_the_books = [russian.books, russian.plan_query_hint, russian.plan_area_query_hint]
    about_the_queries = [
        russian.queries,
        russian.queries_detail,
        russian.rewrite_tool_purpose,
        russian.digest_quote,
    ]

    assert not any("на английском" in text for text in about_the_books)
    assert not any("английск" in text or "по-английски" in text for text in about_the_queries)


def test_both_corpora_word_every_field() -> None:
    for wording in (corpus_language._ENGLISH, corpus_language._RUSSIAN):
        assert all(value.strip() for value in asdict(wording).values())
