from scraper.parser import parse_html

SAMPLE = """
<html>
  <head>
    <title>  Hello World  </title>
    <meta name="description" content="A sample page">
  </head>
  <body>
    <script>var x = 1;</script>
    <h1>Heading</h1>
    <p>Some text here.</p>
    <a href="/about">About</a>
    <a href="page.html">Page</a>
    <a href="https://other.com/x">External</a>
    <a href="mailto:me@example.com">Mail</a>
    <a href="#section">Anchor</a>
    <a href="/about">Dup</a>
  </body>
</html>
"""


def test_extracts_text():
    text, _ = parse_html(SAMPLE, "https://example.com/dir/")
    assert "Heading" in text
    assert "var x" not in text  # script content removed


def test_resolves_and_dedupes_links():
    _, links = parse_html(SAMPLE, "https://example.com/dir/")
    assert "https://example.com/about" in links
    assert "https://example.com/dir/page.html" in links
    assert "https://other.com/x" in links
    # mailto and pure-fragment links dropped, /about not duplicated
    assert not any(l.startswith("mailto:") for l in links)
    assert links.count("https://example.com/about") == 1
