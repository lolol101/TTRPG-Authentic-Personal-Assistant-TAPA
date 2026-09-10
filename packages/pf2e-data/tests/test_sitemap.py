from app.sitemap import filter_by_prefix, parse_sitemap_urls

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
