"""Serialize scraped pages to JSON, CSV, and markdown with incremental update support."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable, TextIO

from .models import Page

DEFAULT_OUTPUT_DIR = "data"
MARKDOWN_DIRNAME = "markdown"
RAW_DATA_FILENAME = "raw_data"

RAW_DATA_CSV_FIELDS = [
    "doc_id",
    "base_url",
    "canonical_url",
    "crawl_dt",
    "doc_last_modified_dt",
    "content_type",
    "content_source_type",
    "scheme_type",
    "scheme_name",
    "lang",
    "doc_version",
    "is_active",
    "status",
    "crawl_depth",
    "normalized_url",
]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def markdown_dir(data_path: Path) -> Path:
    return data_path.parent / MARKDOWN_DIRNAME


def markdown_path(data_path: Path, doc_id: str) -> Path:
    return markdown_dir(data_path) / f"{doc_id}.md"


def read_markdown(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_markdown(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _parse_csv_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _csv_cell(row: dict, field: str) -> str | int | bool:
    value = row.get(field, "")
    if field == "is_active":
        return _parse_csv_bool(value) if isinstance(value, str) else bool(value)
    if field in {"doc_version", "status", "crawl_depth"}:
        return int(value or 0)
    return value


def load_raw_data(path: Path) -> dict[str, dict]:
    """Load page rows from raw_data.csv keyed by canonical_url."""
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = row.get("canonical_url", "")
            if not url:
                continue
            rows[url] = {field: _csv_cell(row, field) for field in RAW_DATA_CSV_FIELDS}
    return rows


def save_raw_data(rows: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RAW_DATA_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows.values():
            out = dict(row)
            if isinstance(out.get("is_active"), bool):
                out["is_active"] = str(out["is_active"])
            writer.writerow(out)


def load_index(path: Path) -> dict[str, dict]:
    """Load page index rows keyed by canonical_url from legacy results.json."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        entries = json.load(fh)
    if not isinstance(entries, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return {entry["canonical_url"]: entry for entry in entries}


def load_links(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return {url: list(links) for url, links in data.items()}


def save_links(links: dict[str, list[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(links, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _load_legacy_metadata_links(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return {
            entry["canonical_url"]: entry.get("links", [])
            for entry in data
            if entry.get("canonical_url")
        }
    return {url: public.get("links", []) for url, public in data.items()}


def content_for_row(data_path: Path, row: dict) -> str:
    """Read page content from markdown, falling back to legacy inline JSON."""
    doc_id = row.get("doc_id", "")
    if doc_id:
        text = read_markdown(markdown_path(data_path, doc_id))
        if text:
            return text
    return row.get("content", "")


def page_row(page: Page) -> dict:
    row = page.to_dict()
    row.pop("links", None)
    row.pop("error", None)
    row.pop("content", None)
    return row


def load_crawl_state(
    raw_data_path: Path,
    json_path: Path,
    links_path: Path,
    *,
    legacy_metadata_path: Path | None = None,
) -> dict[str, dict]:
    """Load crawl state keyed by canonical_url for incremental updates."""
    rows = load_raw_data(raw_data_path)
    if not rows:
        rows = load_index(json_path)

    links = load_links(links_path)
    if not links and legacy_metadata_path is not None:
        links = _load_legacy_metadata_links(legacy_metadata_path)

    state: dict[str, dict] = {}
    for url, row in rows.items():
        content = content_for_row(raw_data_path, row)
        state[url] = {
            "doc_id": row.get("doc_id", ""),
            "base_url": row.get("base_url", ""),
            "canonical_url": url,
            "crawl_dt": row.get("crawl_dt", ""),
            "doc_last_modified_dt": row.get("doc_last_modified_dt", ""),
            "content_hash": content_hash(content) if content else "",
            "doc_version": int(row.get("doc_version", 1)),
            "links": links.get(url, []),
            "crawl_depth": int(row.get("crawl_depth", 0)),
        }
    return state


def load_unparseable(path: Path) -> set[str]:
    """Load URLs where content extraction failed."""
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return set(data)


def save_unparseable(urls: set[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(sorted(urls), fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def update_unparseable(pages: list[Page], path: Path) -> None:
    """Track URLs with no extractable content; drop URLs that succeed later."""
    urls = load_unparseable(path)
    for page in pages:
        url = page.canonical_url
        if not url:
            continue
        if page.has_extractable_content():
            urls.discard(url)
        else:
            urls.add(url)
    save_unparseable(urls, path)


def write_json(pages: Iterable[Page], stream: TextIO) -> None:
    json.dump([page_row(p) for p in pages], stream, indent=2, ensure_ascii=False)
    stream.write("\n")


def resolve_path(filename: str, fmt: str, out_dir: str = DEFAULT_OUTPUT_DIR) -> Path:
    """Resolve where to write output.

    A bare filename (no directory component) is placed inside ``out_dir``;
    a filename with a path is respected as given. A missing extension gets
    ``.{fmt}``. The parent directory is created if needed.
    """
    p = Path(filename)
    if p.suffix == "":
        p = p.with_suffix(f".{fmt}")
    if p.parent == Path("."):
        p = Path(out_dir) / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_incremental(
    pages: list[Page],
    json_path: Path,
    raw_data_path: Path,
    links_path: Path,
    unparseable_path: Path | None = None,
    *,
    legacy_metadata_path: Path | None = None,
) -> tuple[int, int, int]:
    """Write pages incrementally, returning (new, updated, skipped) counts."""
    existing_rows = load_raw_data(raw_data_path)
    if not existing_rows:
        existing_rows = load_index(json_path)

    crawl_state = load_crawl_state(
        raw_data_path,
        json_path,
        links_path,
        legacy_metadata_path=legacy_metadata_path,
    )
    links_by_url = load_links(links_path)
    if not links_by_url and legacy_metadata_path is not None:
        links_by_url = _load_legacy_metadata_links(legacy_metadata_path)

    new_count = 0
    updated_count = 0
    skipped_count = 0

    for page in pages:
        if page.error:
            continue

        url = page.canonical_url
        if url in crawl_state and crawl_state[url].get("doc_id"):
            page.doc_id = crawl_state[url]["doc_id"]
            page.doc_version = int(crawl_state[url].get("doc_version", 1))

        new_hash = content_hash(page.content)

        if url in crawl_state:
            old_hash = crawl_state[url].get("content_hash", "")
            if old_hash == new_hash:
                skipped_count += 1
                continue
            page.doc_version = int(crawl_state[url].get("doc_version", 1)) + 1
            updated_count += 1
        else:
            new_count += 1

        if page.has_extractable_content():
            write_markdown(page.content, markdown_path(raw_data_path, page.doc_id))

        existing_rows[url] = page_row(page)
        links_by_url[url] = page.links

    save_raw_data(existing_rows, raw_data_path)
    save_links(links_by_url, links_path)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8", newline="") as fh:
        json.dump(list(existing_rows.values()), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    if unparseable_path is not None:
        update_unparseable(pages, unparseable_path)

    return new_count, updated_count, skipped_count
