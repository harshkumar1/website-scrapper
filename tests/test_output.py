import io
import json

from scraper.models import Page
from scraper.output import resolve_path, write, write_csv, write_json


def _pages():
    return [
        Page(
            canonical_url="https://example.com",
            status_code=200,
            uuid="abc-123",
            base_url="https://example.com",
            last_updated_on="2026-06-19T00:00:00+00:00",
            content="body text",
            links=["https://example.com/a", "https://example.com/b"],
            depth=0,
            content_type="text/html",
        )
    ]


def test_write_json_roundtrips():
    buf = io.StringIO()
    write_json(_pages(), buf)
    data = json.loads(buf.getvalue())
    assert data[0]["canonical_url"] == "https://example.com"
    assert data[0]["links"] == ["https://example.com/a", "https://example.com/b"]


def test_write_csv_has_requested_columns():
    buf = io.StringIO()
    write_csv(_pages(), buf)
    out = buf.getvalue()
    assert out.startswith("uuid,base_url,canonical_url,last_updated_on,content")
    assert "abc-123" in out
    assert "https://example.com" in out
    assert "body text" in out
    assert "<html>" not in out


def test_resolve_path_puts_bare_name_in_output_dir(tmp_path):
    p = resolve_path("results.csv", "csv", out_dir=str(tmp_path / "out"))
    assert p == tmp_path / "out" / "results.csv"
    assert p.parent.is_dir()  # directory created


def test_resolve_path_adds_extension_and_respects_explicit_dir(tmp_path):
    bare = resolve_path("data", "json", out_dir=str(tmp_path / "out"))
    assert bare.name == "data.json"

    explicit = resolve_path(str(tmp_path / "custom" / "x.json"), "json")
    assert explicit == tmp_path / "custom" / "x.json"
    assert explicit.parent.is_dir()


def test_write_creates_file(tmp_path):
    target = tmp_path / "out" / "r.json"
    written = write(_pages(), "json", target)
    assert written == target
    assert json.loads(target.read_text())[0]["uuid"] == "abc-123"
