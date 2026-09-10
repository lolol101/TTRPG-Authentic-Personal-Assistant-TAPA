from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.models import ParsedPage, RawPage

_TITLE_NOISE_SELECTORS = (".sr-only", ".action-icon", ".item-type")


class UnrecognizedPageError(ValueError):
    """Raised when a page doesn't match any known pf2.ru content template."""


def parse_page(page: RawPage) -> ParsedPage:
    soup = BeautifulSoup(page.html, "lxml")
    content = soup.select_one("#item-content-ru")
    if content is None:
        raise UnrecognizedPageError(
            f"No #item-content-ru container on {page.url} — unsupported page template."
        )

    title = _extract_title(content)
    traits = _extract_traits(content)
    output = content.select_one(".item-output")
    source_book = _extract_source_book(output) if output else None
    body = _extract_body(output) if output else ""

    return ParsedPage(
        url=page.url,
        category=category_from_url(page.url),
        title=title,
        source_book=source_book,
        traits=traits,
        body=body,
        fetched_at=page.fetched_at,
    )


def category_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/", 1)[0] if path else ""


def _extract_title(content: Tag) -> str:
    h1 = content.select_one("h1.h1-header")
    if h1 is None:
        return ""
    for selector in _TITLE_NOISE_SELECTORS:
        for noise in h1.select(selector):
            noise.decompose()
    return h1.get_text(separator=" ", strip=True)


def _extract_traits(content: Tag) -> list[str]:
    return [a.get_text(strip=True) for a in content.select(".item-traits a")]


def _extract_source_book(output: Tag) -> str | None:
    link = output.select_one("a.item-link--source")
    return link.get_text(strip=True) if link else None


def _extract_body(output: Tag) -> str:
    hr = output.find("hr")
    region: Tag = output
    if hr is not None:
        wrapper = BeautifulSoup("<div></div>", "lxml").div
        for sibling in list(hr.next_siblings):
            wrapper.append(sibling.extract())
        region = wrapper

    text = region.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
