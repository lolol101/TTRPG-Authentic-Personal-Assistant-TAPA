import tempfile
from pathlib import Path

import pytest

from services.scraper import AonScraper


class TestScraperLinkExtraction:
    """Tests for the deterministic link-extraction logic (no HTTP)."""

    @pytest.fixture()
    def scraper(self, tmp_path):
        return AonScraper(book_name="test", cache_dir=str(tmp_path))

    def test_extracts_aspx_links(self, scraper):
        html = """
        <html><body>
            <a href="Rules.aspx?ID=123">Rules</a>
            <a href="Spells.aspx">Spells</a>
            <a href="/images/logo.png">Logo</a>
        </body></html>
        """
        links = scraper._extract_links("https://2e.aonprd.com/Sources.aspx", html)
        assert len(links) == 2
        assert all(".aspx" in lnk.lower() for lnk in links)

    def test_ignores_external_links(self, scraper):
        html = '<html><body><a href="https://evil.com/Hack.aspx">Bad</a></body></html>'
        links = scraper._extract_links("https://2e.aonprd.com/Sources.aspx", html)
        assert links == []

    def test_deduplicates(self, scraper):
        html = """
        <html><body>
            <a href="Rules.aspx?ID=1">A</a>
            <a href="Rules.aspx?ID=1">B</a>
        </body></html>
        """
        links = scraper._extract_links("https://2e.aonprd.com/Sources.aspx", html)
        assert len(links) == 1


class TestScraperCache:
    def test_cache_write_and_read(self, tmp_path):
        scraper = AonScraper(book_name="cache_test", cache_dir=str(tmp_path))
        url = "https://example.com/Test.aspx"
        scraper._write_cache(url, "<html>cached</html>")
        assert scraper._read_cache(url) == "<html>cached</html>"

    def test_cache_miss(self, tmp_path):
        scraper = AonScraper(book_name="cache_test", cache_dir=str(tmp_path))
        assert scraper._read_cache("https://example.com/Missing.aspx") is None


class TestTitleExtraction:
    def test_from_title_tag(self):
        html = "<html><head><title>My Page</title></head><body></body></html>"
        assert AonScraper._title_from_html(html) == "My Page"

    def test_from_h1_fallback(self):
        html = "<html><body><h1>Heading</h1></body></html>"
        assert AonScraper._title_from_html(html) == "Heading"

    def test_untitled_fallback(self):
        html = "<html><body><p>No title or heading</p></body></html>"
        assert AonScraper._title_from_html(html) == "Untitled"
