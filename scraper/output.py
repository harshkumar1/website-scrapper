"""Serialize scraped pages to JSON or CSV with incremental update support."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable, TextIO

from .models import Page

DEFAULT_OUTPUT_DIR = "output"

_CSV_FIELDS = [
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
    "content",
]

_META_FIELDS = [
    "doc_id",
    "base_url",
    "canonical_url",
    "crawl_dt",
    "doc_last_modified_dt",
    "content_hash",
]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_metadata(path: Path) -> dict[str, dict]:
    """Load the metadata JSON index keyed by normalized_url."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        entries = json.load(fh)
    return {entry["canonical_url"]: entry for entry in entries}


def save_metadata(meta: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(list(meta.values()), fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def load_existing_csv(path: Path) -> dict[str, dict]:
    """Load existing CSV rows keyed by canonical_url."""
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = row.get("canonical_url", "")
            if url:
                rows[url] = row
    return rows


def write_json(pages: Iterable[Page], stream: TextIO) -> None:
    json.dump([p.to_dict() for p in pages], stream, indent=2, ensure_ascii=False)
    stream.write("\n")


def write_csv(rows: dict[str, dict], stream: TextIO) -> None:
    writer = csv.DictWriter(stream, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows.values():
        writer.writerow(row)


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
    csv_path: Path,
    json_path: Path,
    meta_path: Path,
) -> tuple[int, int, int]:
    """Write pages incrementally, returning (new, updated, skipped) counts."""
    existing_csv = load_existing_csv(csv_path)
    metadata = load_metadata(meta_path)

    new_count = 0
    updated_count = 0
    skipped_count = 0

    for page in pages:
        if page.error:
            continue

        url = page.canonical_url
        new_hash = content_hash(page.content)

        if url in metadata:
            old_hash = metadata[url].get("content_hash", "")
            if old_hash == new_hash:
                skipped_count += 1
                continue
            page.doc_version = int(metadata[url].get("doc_version", 1)) + 1
            updated_count += 1
        else:
            new_count += 1

        row = page.to_dict()
        row.pop("links", None)
        row.pop("error", None)
        existing_csv[url] = row

        metadata[url] = {
            "doc_id": page.doc_id,
            "base_url": page.base_url,
            "canonical_url": page.canonical_url,
            "crawl_dt": page.crawl_dt,
            "doc_last_modified_dt": page.doc_last_modified_dt,
            "content_hash": new_hash,
            "doc_version": page.doc_version,
            "links": page.links,
            "crawl_depth": page.crawl_depth,
        }

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        write_csv(existing_csv, fh)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    all_pages_data = list(existing_csv.values())
    with open(json_path, "w", encoding="utf-8", newline="") as fh:
        json.dump(all_pages_data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    save_metadata(metadata, meta_path)

    return new_count, updated_count, skipped_count
