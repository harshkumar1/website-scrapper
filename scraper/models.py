"""Data structures produced by the scraper."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Page:
    """A single scraped page and the data extracted from it."""

    canonical_url: str
    status_code: int
    uuid: str = ""
    base_url: str = ""
    last_updated_on: str = ""
    content: str = ""
    links: list[str] = field(default_factory=list)
    depth: int = 0
    content_type: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
