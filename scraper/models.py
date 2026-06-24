"""Data structures produced by the scraper."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Page:
    """A single scraped page and the data extracted from it."""

    doc_id: str = ""
    base_url: str = ""
    canonical_url: str = ""
    crawl_dt: str = ""
    doc_last_modified_dt: str = ""
    content_type: str = ""
    content_source_type: str = "web"
    scheme_type: str = ""
    scheme_name: str = ""
    lang: str = "en"
    doc_version: int = 1
    is_active: bool = True
    status: int = 0
    crawl_depth: int = 0
    normalized_url: str = ""
    content: str = ""
    links: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
