"""Breadth-first website crawler with politeness controls."""

from __future__ import annotations

import logging
import time
import uuid as uuidlib
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .models import Page
from .parser import parse_html

logger = logging.getLogger(__name__)


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

        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

        self._robots = self._load_robots(parsed) if respect_robots else None

    def _load_robots(self, parsed) -> RobotFileParser | None:
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            logger.debug("Loaded robots.txt from %s", robots_url)
            return rp
        except Exception as exc:  # network/parse errors -> allow everything
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
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(self.start_url, 0)])

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
        crawled_at = datetime.now(timezone.utc).isoformat()
        page = Page(
            canonical_url=url,
            status_code=0,
            uuid=str(uuidlib.uuid4()),
            base_url=self.base_url,
            last_updated_on=crawled_at,
            depth=depth,
        )

        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            page.error = str(exc)
            return page

        page.status_code = resp.status_code
        page.content_type = resp.headers.get("Content-Type", "")
        # The canonical URL is the actual fetched URL (after redirects).
        page.canonical_url = resp.url

        if resp.status_code != 200 or "html" not in page.content_type.lower():
            return page

        text, links = parse_html(resp.text, resp.url)
        page.content = text
        page.links = links
        return page
