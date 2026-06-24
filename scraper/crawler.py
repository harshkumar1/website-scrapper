"""Breadth-first website crawler with politeness controls."""

from __future__ import annotations

import io
import logging
import tempfile
import time
import uuid as uuidlib
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import pdfplumber
import requests

from .models import Page
from .parser import parse_html

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalize a URL by removing fragments, trailing slashes, and lowercasing the scheme/host."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


class Crawler:
    """Crawl a website starting from a seed URL.

    The crawler stays within the seed's domain, respects ``robots.txt`` by
    default, rate-limits requests, and stops once ``max_pages`` or
    ``max_depth`` is reached.
    """

    def __init__(
        self,
        start_url: str,
        *,
        max_pages: int = 50,
        max_depth: int = 3,
        delay: float = 0.5,
        timeout: float = 10.0,
        user_agent: str = "website-scrapper/0.1 (+https://github.com/)",
        respect_robots: bool = True,
        same_domain_only: bool = True,
        already_visited: set[str] | None = None,
        frontier: list[tuple[str, int]] | None = None,
    ) -> None:
        self.start_url = start_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.timeout = timeout
        self.same_domain_only = same_domain_only
        self.respect_robots = respect_robots

        parsed = urlparse(start_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid start URL: {start_url!r}")
        self.domain = parsed.netloc
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.scheme_type = parsed.scheme.upper()

        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

        self._robots = self._load_robots(parsed) if respect_robots else None
        self._already_visited = already_visited or set()
        self._frontier = frontier or []

    def _load_robots(self, parsed) -> RobotFileParser | None:
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            logger.debug("Loaded robots.txt from %s", robots_url)
            return rp
        except Exception as exc:
            logger.warning("Could not read robots.txt (%s); proceeding", exc)
            return None

    def _allowed(self, url: str) -> bool:
        if self._robots is None:
            return True
        return self._robots.can_fetch(self.session.headers["User-Agent"], url)

    def _in_scope(self, url: str) -> bool:
        if not self.same_domain_only:
            return True
        return urlparse(url).netloc == self.domain

    def crawl(self) -> list[Page]:
        """Run the crawl and return the list of scraped pages."""
        pages: list[Page] = []
        visited: set[str] = set(self._already_visited)
        queue: deque[tuple[str, int]] = deque()
        queue.append((self.start_url, 0))
        for frontier_url, frontier_depth in self._frontier:
            if frontier_url not in visited and self._in_scope(frontier_url):
                queue.append((frontier_url, frontier_depth))

        while queue and len(pages) < self.max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > self.max_depth:
                continue
            visited.add(url)

            if not self._allowed(url):
                logger.info("Blocked by robots.txt: %s", url)
                continue

            page = self._fetch(url, depth)
            pages.append(page)
            logger.info("[%d/%d] depth=%d %s", len(pages), self.max_pages, depth, url)

            if depth < self.max_depth and not page.error:
                for link in page.links:
                    if link not in visited and self._in_scope(link):
                        queue.append((link, depth + 1))

            if self.delay:
                time.sleep(self.delay)

        return pages

    def _fetch(self, url: str, depth: int) -> Page:
        now = datetime.now(timezone.utc).isoformat()
        page = Page(
            doc_id=str(uuidlib.uuid4()),
            base_url=self.base_url,
            canonical_url=url,
            crawl_dt=now,
            doc_last_modified_dt=now,
            crawl_depth=depth,
            scheme_type=self.scheme_type,
            scheme_name=self.domain,
            normalized_url=_normalize_url(url),
        )

        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            page.error = str(exc)
            return page

        page.status = resp.status_code
        page.content_type = resp.headers.get("Content-Type", "")
        page.canonical_url = resp.url
        page.normalized_url = _normalize_url(resp.url)

        last_modified = resp.headers.get("Last-Modified", "")
        if last_modified:
            page.doc_last_modified_dt = last_modified

        content_lang = resp.headers.get("Content-Language", "")
        if content_lang:
            page.lang = content_lang.split(",")[0].strip()

        if resp.status_code != 200:
            page.is_active = False
            return page

        ct = page.content_type.lower()

        if "html" in ct:
            text, links = parse_html(resp.text, resp.url)
            page.content = text
            page.links = links
        elif "pdf" in ct or url.lower().endswith(".pdf"):
            page.content = self._extract_pdf_text(resp.content)
            page.content_source_type = "pdf"
        else:
            page.is_active = False

        return page

    @staticmethod
    def _extract_pdf_text(data: bytes) -> str:
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                parts = []
                for pg in pdf.pages:
                    text = pg.extract_text()
                    if text:
                        parts.append(text)
                return " ".join(" ".join(parts).split())
        except Exception as exc:
            logger.warning("Failed to extract PDF text: %s", exc)
            return ""
