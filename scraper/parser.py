"""HTML parsing helpers built on BeautifulSoup."""

from __future__ import annotations

from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup


def parse_html(html: str, base_url: str) -> tuple[str, list[str]]:
    """Extract (text, links) from an HTML document.

    Links are resolved against ``base_url`` and returned absolute, with
    fragments stripped and duplicates removed (order preserved).
    """
    soup = BeautifulSoup(html, "lxml")

    # Drop non-content elements before extracting visible text.
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())

    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute, _ = urldefrag(urljoin(base_url, href))
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    return text, links
