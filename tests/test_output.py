import io
import json

from scraper.models import Page
from scraper.output import (
    content_hash,
    load_metadata,
    resolve_path,
    save_metadata,
    write_csv,
    write_incremental,
    write_json,
)


def _pages():
    return [
        Page(
            doc_id="abc-123",
            base_url="https://example.com",
            canonical_url="https://example.com",
            crawl_dt="2026-06-19T00:00:00+00:00",
            doc_last_modified_dt="2026-06-19T00:00:00+00:00",
            content_type="text/html",
            content="body text",
            links=["https://example.com/a", "https://example.com/b"],
            crawl_depth=0,
            status=200,
            normalized_url="https://example.com/",
        )
    ]


def test_write_json_roundtrips():
    buf = io.StringIO()
    write_json(_pages(), buf)
    data = json.loads(buf.getvalue())
    assert data[0]["canonical_url"] == "https://example.com"
    assert data[0]["links"] == ["https://example.com/a", "https://example.com/b"]


def test_write_csv_has_requested_columns():
    rows = {"https://example.com": _pages()[0].to_dict()}
    buf = io.StringIO()
    write_csv(rows, buf)
    out = buf.getvalue()
    assert out.startswith("doc_id,base_url,canonical_url,crawl_dt,doc_last_modified_dt")
    assert "abc-123" in out
    assert "body text" in out


def test_resolve_path_puts_bare_name_in_output_dir(tmp_path):
    p = resolve_path("results.csv", "csv", out_dir=str(tmp_path / "out"))
    assert p == tmp_path / "out" / "results.csv"
    assert p.parent.is_dir()


def test_resolve_path_adds_extension_and_respects_explicit_dir(tmp_path):
    bare = resolve_path("data", "json", out_dir=str(tmp_path / "out"))
    assert bare.name == "data.json"

    explicit = resolve_path(str(tmp_path / "custom" / "x.json"), "json")
    assert explicit == tmp_path / "custom" / "x.json"
    assert explicit.parent.is_dir()


def test_write_incremental_new_pages(tmp_path):
    csv_p = tmp_path / "out.csv"
    json_p = tmp_path / "out.json"
    meta_p = tmp_path / "out_metadata.json"

    pages = _pages()
    new, updated, skipped = write_incremental(pages, csv_p, json_p, meta_p)

    assert new == 1
    assert updated == 0
    assert skipped == 0
    assert csv_p.exists()
    assert meta_p.exists()

    meta = load_metadata(meta_p)
    assert "https://example.com" in meta
    assert meta["https://example.com"]["content_hash"] == content_hash("body text")


def test_write_incremental_skips_unchanged(tmp_path):
    csv_p = tmp_path / "out.csv"
    json_p = tmp_path / "out.json"
    meta_p = tmp_path / "out_metadata.json"

    pages = _pages()
    write_incremental(pages, csv_p, json_p, meta_p)

    new, updated, skipped = write_incremental(pages, csv_p, json_p, meta_p)
    assert new == 0
    assert updated == 0
    assert skipped == 1


def test_write_incremental_updates_changed(tmp_path):
    csv_p = tmp_path / "out.csv"
    json_p = tmp_path / "out.json"
    meta_p = tmp_path / "out_metadata.json"

    pages = _pages()
    write_incremental(pages, csv_p, json_p, meta_p)

    pages[0].content = "new body text"
    new, updated, skipped = write_incremental(pages, csv_p, json_p, meta_p)
    assert new == 0
    assert updated == 1
    assert skipped == 0

    meta = load_metadata(meta_p)
    assert meta["https://example.com"]["doc_version"] == 2
