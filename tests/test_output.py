import csv
import io
import json
from pathlib import Path

from scraper.models import Page
from scraper.output import (
    RAW_DATA_CSV_FIELDS,
    content_hash,
    load_crawl_state,
    load_index,
    load_raw_data,
    load_unparseable,
    markdown_path,
    read_markdown,
    resolve_path,
    update_unparseable,
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


def test_write_json_omits_content_and_links():
    buf = io.StringIO()
    write_json(_pages(), buf)
    data = json.loads(buf.getvalue())
    assert data[0]["canonical_url"] == "https://example.com"
    assert "content" not in data[0]
    assert "links" not in data[0]


def test_resolve_path_puts_bare_name_in_output_dir(tmp_path):
    p = resolve_path("results.json", "json", out_dir=str(tmp_path / "out"))
    assert p == tmp_path / "out" / "results.json"
    assert p.parent.is_dir()


def test_resolve_path_adds_extension_and_respects_explicit_dir(tmp_path):
    bare = resolve_path("data", "json", out_dir=str(tmp_path / "out"))
    assert bare.name == "data.json"

    explicit = resolve_path(str(tmp_path / "custom" / "x.json"), "json")
    assert explicit == tmp_path / "custom" / "x.json"
    assert explicit.parent.is_dir()


def test_write_incremental_new_pages(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"

    pages = _pages()
    new, updated, skipped = write_incremental(pages, json_p, raw_p, links_p)

    assert new == 1
    assert updated == 0
    assert skipped == 0
    assert json_p.exists()
    assert raw_p.exists()
    assert links_p.exists()

    rows = load_raw_data(raw_p)
    assert "https://example.com" in rows
    assert rows["https://example.com"]["doc_id"] == "abc-123"
    assert read_markdown(markdown_path(raw_p, "abc-123")) == "body text"

    with open(raw_p, encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == RAW_DATA_CSV_FIELDS

    state = load_crawl_state(raw_p, json_p, links_p)
    assert state["https://example.com"]["content_hash"] == content_hash("body text")
    assert state["https://example.com"]["links"] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_write_incremental_skips_unchanged(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"

    pages = _pages()
    write_incremental(pages, json_p, raw_p, links_p)

    new, updated, skipped = write_incremental(pages, json_p, raw_p, links_p)
    assert new == 0
    assert updated == 0
    assert skipped == 1


def test_write_incremental_updates_changed_and_keeps_doc_id(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"

    pages = _pages()
    write_incremental(pages, json_p, raw_p, links_p)

    pages[0].doc_id = "should-not-change"
    pages[0].content = "new body text"
    new, updated, skipped = write_incremental(pages, json_p, raw_p, links_p)
    assert new == 0
    assert updated == 1
    assert skipped == 0

    rows = load_raw_data(raw_p)
    assert rows["https://example.com"]["doc_id"] == "abc-123"
    assert read_markdown(markdown_path(raw_p, "abc-123")) == "new body text"

    state = load_crawl_state(raw_p, json_p, links_p)
    assert state["https://example.com"]["doc_version"] == 2


def test_update_unparseable_adds_and_dedupes(tmp_path):
    path = tmp_path / "unparseable.json"
    empty_pdf = Page(
        canonical_url="https://example.com/scan.pdf",
        status=200,
        content_type="application/pdf",
        content_source_type="pdf",
    )
    broken = Page(
        canonical_url="https://example.com/image.png",
        status=200,
        content_type="image/png",
    )

    update_unparseable([empty_pdf, broken], path)
    assert load_unparseable(path) == {
        "https://example.com/image.png",
        "https://example.com/scan.pdf",
    }

    update_unparseable([empty_pdf], path)
    assert load_unparseable(path) == {
        "https://example.com/image.png",
        "https://example.com/scan.pdf",
    }


def test_update_unparseable_removes_when_content_succeeds(tmp_path):
    path = tmp_path / "unparseable.json"
    url = "https://example.com/scan.pdf"
    update_unparseable(
        [Page(canonical_url=url, status=200, content_type="application/pdf", content="")],
        path,
    )
    assert url in load_unparseable(path)

    update_unparseable(
        [
            Page(
                canonical_url=url,
                status=200,
                content_type="application/pdf",
                content="extracted text",
            )
        ],
        path,
    )
    assert load_unparseable(path) == set()


def test_write_incremental_writes_unparseable_file(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"
    unparseable_p = tmp_path / "out_unparseable.json"

    pages = _pages()
    pages.append(
        Page(
            canonical_url="https://example.com/empty.pdf",
            status=200,
            content_type="application/pdf",
            content_source_type="pdf",
        )
    )

    write_incremental(pages, json_p, raw_p, links_p, unparseable_p)

    assert load_unparseable(unparseable_p) == {"https://example.com/empty.pdf"}


def test_load_crawl_state_reads_legacy_inline_content(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"
    url = "https://example.com"

    json_p.write_text(
        json.dumps(
            [
                {
                    "doc_id": "abc-123",
                    "canonical_url": url,
                    "content": "legacy inline body",
                    "doc_version": 1,
                    "crawl_depth": 0,
                }
            ]
        ),
        encoding="utf-8",
    )

    state = load_crawl_state(raw_p, json_p, links_p)
    assert state[url]["content_hash"] == content_hash("legacy inline body")


def test_load_crawl_state_reads_legacy_metadata_links(tmp_path):
    json_p = tmp_path / "out.json"
    raw_p = tmp_path / "raw_data.csv"
    links_p = tmp_path / "raw_data_links.json"
    legacy_meta_p = tmp_path / "out_metadata.json"
    url = "https://example.com"

    json_p.write_text(
        json.dumps([{"doc_id": "abc-123", "canonical_url": url, "doc_version": 1, "crawl_depth": 0}]),
        encoding="utf-8",
    )
    legacy_meta_p.write_text(
        json.dumps({url: {"crawl_dt": "t", "doc_last_modified_dt": "t", "links": ["https://example.com/a"]}}),
        encoding="utf-8",
    )

    state = load_crawl_state(raw_p, json_p, links_p, legacy_metadata_path=legacy_meta_p)
    assert state[url]["links"] == ["https://example.com/a"]
