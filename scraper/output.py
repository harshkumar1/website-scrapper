"""Serialize scraped pages to JSON or CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, TextIO

from .models import Page

DEFAULT_OUTPUT_DIR = "output"

_CSV_FIELDS = [
    "uuid",
    "base_url",
    "canonical_url",
    "last_updated_on",
    "content",
]


def write_json(pages: Iterable[Page], stream: TextIO) -> None:
    json.dump([p.to_dict() for p in pages], stream, indent=2, ensure_ascii=False)
    stream.write("\n")


def write_csv(pages: Iterable[Page], stream: TextIO) -> None:
    # Column names match Page field names directly, so to_dict() feeds the
    # writer with no remapping; extra Page fields are ignored.
    writer = csv.DictWriter(stream, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for page in pages:
        writer.writerow(page.to_dict())


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


def write(pages: Iterable[Page], fmt: str, path: Path | str) -> Path:
    """Write ``pages`` as ``fmt`` ('json' or 'csv') to ``path``.

    Returns the path actually written to.
    """
    pages = list(pages)
    writer = {"json": write_json, "csv": write_csv}[fmt]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer(pages, fh)
    return path
