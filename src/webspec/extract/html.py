"""HTML to readable text.

Extracted from ClayHome ``providers/http_fetcher.py::_extract``. selectolax is
the one runtime dependency this package has: it is a C parser, roughly an order
of magnitude faster than BeautifulSoup, and the extraction runs on every page.
"""

from __future__ import annotations

from dataclasses import dataclass

from selectolax.parser import HTMLParser

#: Markup that carries no readable content. Removed before text extraction, or
#: a page's text is mostly its analytics snippets.
NOISE_TAGS = ("script", "style", "noscript", "svg", "template")


@dataclass(slots=True, frozen=True)
class ExtractedContent:
    title: str | None
    text: str
    language: str | None


def extract_content(html: str) -> ExtractedContent:
    """Title, readable text, and declared language.

    The language is whatever the document claims in ``<html lang>``, reduced to
    its primary subtag. It is a claim by the page, not a detection result, and
    callers that need certainty should detect it from the text instead.
    """
    tree = HTMLParser(html)
    for tag in NOISE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else None

    language = None
    html_node = tree.css_first("html")
    if html_node:
        language = (html_node.attributes.get("lang") or "").split("-")[0] or None

    body = tree.body or tree.root
    raw = body.text(separator="\n", strip=True) if body else ""
    # Markup extraction leaves long runs of blank lines behind.
    lines = [line.strip() for line in raw.splitlines()]
    text = "\n".join(line for line in lines if line)

    return ExtractedContent(title=title or None, text=text, language=language)


def visible_text_length(html: str) -> int:
    """Readable characters in a document.

    Used to tell a real page from a JavaScript shell: a shell is many kilobytes
    of markup that renders almost nothing.
    """
    return len(extract_content(html).text)
