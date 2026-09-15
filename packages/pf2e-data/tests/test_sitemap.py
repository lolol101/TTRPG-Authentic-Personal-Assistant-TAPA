import httpx
import pytest

from app.scraper import SiteBlockedError
from app.sitemap import fetch_sitemap_urls, filter_by_prefix, parse_sitemap_urls

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://pf2.ru/actions/strike</loc></url>
    <url><loc>https://pf2.ru/actions/grapple</loc></url>
    <url><loc>https://pf2.ru/ancestries/dwarf</loc></url>
    <url><loc>https://pf2.ru/classes/wizard</loc></url>
</urlset>
"""


def test_parse_sitemap_urls_extracts_all_locs() -> None:
    urls = parse_sitemap_urls(SAMPLE_XML)

    assert urls == [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
        "https://pf2.ru/ancestries/dwarf",
        "https://pf2.ru/classes/wizard",
    ]


def test_filter_by_prefix_keeps_matching_only() -> None:
    urls = parse_sitemap_urls(SAMPLE_XML)

    actions = filter_by_prefix(urls, path_prefix="/actions/")

    assert actions == [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
    ]


def test_filter_by_prefix_respects_limit_and_order() -> None:
    urls = parse_sitemap_urls(SAMPLE_XML)

    actions = filter_by_prefix(urls, path_prefix="/actions/", limit=1)

    assert actions == ["https://pf2.ru/actions/strike"]


def test_filter_by_prefix_no_match_returns_empty() -> None:
    urls = parse_sitemap_urls(SAMPLE_XML)

    assert filter_by_prefix(urls, path_prefix="/spells/") == []


def test_a_page_listed_twice_is_fetched_once() -> None:
    """pf2.ru repeats entries; without this a quarter of the crawl was wasted
    re-downloading pages it already had — against a site that rate-limits."""
    urls = [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
        "https://pf2.ru/actions/strike",
    ]

    assert filter_by_prefix(urls, path_prefix="/actions/") == [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
    ]


def test_deduplication_keeps_the_first_position() -> None:
    """Order is what makes --limit reproducible across runs."""
    urls = ["https://pf2.ru/actions/b", "https://pf2.ru/actions/a", "https://pf2.ru/actions/b"]

    assert filter_by_prefix(urls, path_prefix="/actions/")[0].endswith("/b")


def test_the_limit_counts_distinct_pages() -> None:
    """Counting repeats toward the limit would silently shrink a --limit run."""
    urls = [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
    ]

    assert filter_by_prefix(urls, path_prefix="/actions/", limit=2) == [
        "https://pf2.ru/actions/strike",
        "https://pf2.ru/actions/grapple",
    ]


def test_a_blocked_sitemap_raises_site_blocked_error(monkeypatch) -> None:
    """pf2.ru's block refuses sitemap.xml itself, not only pages under it — a
    bare HTTPStatusError here escaped every retry loop, which only catches
    SiteBlockedError, and crashed the whole run instead of pausing."""

    def _refused(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(403, request=request)

    monkeypatch.setattr(httpx, "get", _refused)

    with pytest.raises(SiteBlockedError):
        fetch_sitemap_urls("https://pf2.ru/sitemap.xml", user_agent="test-agent")


def test_a_genuinely_missing_sitemap_still_raises_plainly(monkeypatch) -> None:
    """Not every failure is a block — a 404 sitemap is a real error and
    should surface as one, not be swallowed as "just retry"."""

    def _missing(url, headers=None, timeout=None):
        request = httpx.Request("GET", url)
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx, "get", _missing)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_sitemap_urls("https://pf2.ru/sitemap.xml", user_agent="test-agent")
