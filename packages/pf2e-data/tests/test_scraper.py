import httpx
import pytest

from app.models import RawPage
from app.scraper import Scraper, SiteBlockedError


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls = 0

    def get(self, url: str, headers: dict, timeout: float) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(self.response_text)


@pytest.fixture()
def scraper(tmp_path):
    return Scraper(cache_dir=str(tmp_path), rate_limit_seconds=0.0)


def test_fetch_hits_network_on_first_call(scraper) -> None:
    client = _FakeClient("<html>fresh</html>")

    page = scraper.fetch("https://pf2.ru/actions/strike", client)

    assert page.html == "<html>fresh</html>"
    assert client.calls == 1


def test_fetch_uses_cache_on_second_call(scraper) -> None:
    client = _FakeClient("<html>fresh</html>")
    scraper.fetch("https://pf2.ru/actions/strike", client)

    page = scraper.fetch("https://pf2.ru/actions/strike", client)

    assert page.html == "<html>fresh</html>"
    assert client.calls == 1  # second call was served from disk cache


def test_different_urls_get_different_cache_entries(scraper) -> None:
    client = _FakeClient("<html>content</html>")

    scraper.fetch("https://pf2.ru/actions/strike", client)
    scraper.fetch("https://pf2.ru/actions/grapple", client)

    assert client.calls == 2


def test_fetch_all_returns_pages_for_every_url(scraper, monkeypatch) -> None:
    def _fake_client_get(self, url, headers, timeout):
        return _FakeResponse(f"<html>{url}</html>")

    monkeypatch.setattr(httpx.Client, "get", _fake_client_get)

    pages = list(
        scraper.fetch_all(["https://pf2.ru/actions/strike", "https://pf2.ru/actions/grapple"])
    )

    assert [p.url for p in pages] == [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
    ]


def test_a_dead_link_does_not_take_the_rest_of_the_section_with_it(scraper, monkeypatch) -> None:
    """pf2.ru's sitemap lists URLs that now answer 500; hundreds of good
    pages sit behind them."""

    def _fake_get(self, url, headers=None, timeout=None):
        if "broken" in url:
            response = httpx.Response(500, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError("boom", request=response.request, response=response)
        return httpx.Response(200, text=f"<html>{url}</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", _fake_get)

    pages = list(
        scraper.fetch_all(
            ["https://pf2.ru/a/one", "https://pf2.ru/a/broken", "https://pf2.ru/a/two"]
        )
    )

    assert [page.url for page in pages] == ["https://pf2.ru/a/one", "https://pf2.ru/a/two"]
    assert scraper.unreachable == ["https://pf2.ru/a/broken"]


def _refused(url: str, status: int = 429) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        str(status), request=httpx.Request("GET", url), response=httpx.Response(status)
    )


def _patient_scraper(tmp_path, waits: list[float], **overrides) -> Scraper:
    options = {"refusal_backoff_seconds": 60.0, "refusal_backoff_max_seconds": 900.0}
    options.update(overrides)
    return Scraper(cache_dir=str(tmp_path), rate_limit_seconds=0, sleep=waits.append, **options)


def test_a_refused_page_is_waited_for_not_skipped(monkeypatch, tmp_path) -> None:
    """pf2.ru answers 429 to every uncached page while the limit lasts. Pages
    from the cache in between used to reset the block counter, so the run
    skipped every new page and reported itself finished with holes."""
    waits: list[float] = []
    scraper = _patient_scraper(tmp_path, waits)
    attempts = {"n": 0}

    def _refused_twice(url, client):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise _refused(url)
        return RawPage(url=url, html="<html></html>", fetched_at="now")

    monkeypatch.setattr(scraper, "fetch", _refused_twice)

    pages = list(scraper.fetch_all(["https://pf2.ru/feats/power attack"]))

    assert [page.url for page in pages] == ["https://pf2.ru/feats/power attack"]
    assert scraper.unreachable == []
    assert len(waits) == 2


def test_waits_grow_and_stop_growing_at_the_cap(monkeypatch, tmp_path) -> None:
    waits: list[float] = []
    scraper = _patient_scraper(tmp_path, waits, refusal_max_wait_seconds=10_000)
    attempts = {"n": 0}

    def _refused_six_times(url, client):
        attempts["n"] += 1
        if attempts["n"] <= 6:
            raise _refused(url, 403)
        return RawPage(url=url, html="<html></html>", fetched_at="now")

    monkeypatch.setattr(scraper, "fetch", _refused_six_times)

    list(scraper.fetch_all(["https://pf2.ru/spells/shield"]))

    assert waits == [60.0, 120.0, 240.0, 480.0, 900.0, 900.0]


def test_a_refusal_that_outlasts_the_patience_stops_the_section(monkeypatch, tmp_path) -> None:
    waits: list[float] = []
    scraper = _patient_scraper(tmp_path, waits, refusal_max_wait_seconds=1000)

    def _always_refused(url, client):
        raise _refused(url)

    monkeypatch.setattr(scraper, "fetch", _always_refused)

    with pytest.raises(SiteBlockedError):
        list(scraper.fetch_all(["https://pf2.ru/spells/shield", "https://pf2.ru/spells/fear"]))

    assert sum(waits) <= 1000
    assert scraper.unreachable == []


def test_the_wait_starts_over_for_the_next_page(monkeypatch, tmp_path) -> None:
    waits: list[float] = []
    scraper = _patient_scraper(tmp_path, waits)
    refused_once: set[str] = set()

    def _each_refused_once(url, client):
        if url not in refused_once:
            refused_once.add(url)
            raise _refused(url)
        return RawPage(url=url, html="<html></html>", fetched_at="now")

    monkeypatch.setattr(scraper, "fetch", _each_refused_once)

    list(scraper.fetch_all(["https://pf2.ru/a/one", "https://pf2.ru/a/two"]))

    assert waits == [60.0, 60.0]


def test_a_run_of_blocks_stops_the_section(monkeypatch, tmp_path) -> None:
    """A dead link and a rate-limit block both arrive as an error, but they
    mean opposite things: one page is gone for good, the whole section is
    merely unavailable for now. Skipping through a block marks hundreds of
    live pages as unreachable and reports the section done."""
    scraper = Scraper(
        cache_dir=str(tmp_path),
        rate_limit_seconds=0,
        sleep=lambda _: None,
        refusal_max_wait_seconds=0,
    )

    def _always_blocked(url, client):
        raise httpx.HTTPStatusError(
            "403", request=httpx.Request("GET", url), response=httpx.Response(403)
        )

    monkeypatch.setattr(scraper, "fetch", _always_blocked)

    with pytest.raises(SiteBlockedError):
        list(scraper.fetch_all([f"https://pf2.ru/spells/s{i}" for i in range(50)]))


def test_scattered_dead_links_are_still_skipped(monkeypatch, tmp_path) -> None:
    """The sitemap genuinely lists URLs that 404; one must not end the run."""
    scraper = Scraper(cache_dir=str(tmp_path), rate_limit_seconds=0)
    urls = [f"https://pf2.ru/spells/s{i}" for i in range(20)]

    def _every_third_is_dead(url, client):
        if int(url[-1]) % 3 == 0:
            raise httpx.HTTPStatusError(
                "404", request=httpx.Request("GET", url), response=httpx.Response(404)
            )
        return RawPage(url=url, html="<html></html>", fetched_at="now")

    monkeypatch.setattr(scraper, "fetch", _every_third_is_dead)

    pages = list(scraper.fetch_all(urls))

    assert len(pages) > 10
    assert scraper.unreachable


def test_a_block_after_good_pages_keeps_what_was_read(monkeypatch, tmp_path) -> None:
    scraper = Scraper(
        cache_dir=str(tmp_path),
        rate_limit_seconds=0,
        sleep=lambda _: None,
        refusal_max_wait_seconds=0,
    )
    seen = []

    def _blocked_after_five(url, client):
        if len(seen) >= 5:
            raise httpx.HTTPStatusError(
                "403", request=httpx.Request("GET", url), response=httpx.Response(403)
            )
        seen.append(url)
        return RawPage(url=url, html="<html></html>", fetched_at="now")

    monkeypatch.setattr(scraper, "fetch", _blocked_after_five)

    pages = []
    with pytest.raises(SiteBlockedError):
        for page in scraper.fetch_all([f"https://pf2.ru/x{i}" for i in range(40)]):
            pages.append(page)

    assert len(pages) == 5
