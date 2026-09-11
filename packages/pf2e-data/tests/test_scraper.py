import httpx
import pytest

from app.scraper import Scraper


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
