# website-scrapper

A polite, configurable website scraper. Crawls a site starting from a seed
URL, extracts each page's title, description, visible text, and links, and
writes the results to JSON or CSV.

## Features

- Breadth-first crawl with configurable page and depth limits
- Stays within the seed domain by default (opt out with `--allow-external`)
- Honors `robots.txt` (opt out with `--ignore-robots`)
- Polite rate limiting between requests (`--delay`)
- JSON or CSV output, to a file or stdout
- Resolves relative links to absolute URLs and de-duplicates them

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Results are always written to a file inside an output folder (`output/` by
default). When `-o` is omitted, the filename is auto-generated from the
domain and a timestamp, e.g. `output/example.com_20260619_112232.json`.

```bash
# Crawl up to 50 pages (default) -> output/<domain>_<timestamp>.json
website-scrapper https://example.com

# CSV instead -> output/<domain>_<timestamp>.csv
website-scrapper https://example.com -f csv

# Custom filename (bare name lands in the output folder) -> output/results.csv
website-scrapper https://example.com -f csv -o results.csv

# Custom output folder
website-scrapper https://example.com --output-dir data

# A path with directories is respected as-is (folder created if needed)
website-scrapper https://example.com -o reports/run1.json

# Be quicker about it (no delay), follow external links
website-scrapper https://example.com --delay 0 --allow-external

# Common real run: cap pages/depth, CSV, custom name
website-scrapper https://example.com -f csv -o results.csv
```

You can also run it as a module: `python -m scraper https://example.com`.

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Output filename (auto from domain+timestamp if omitted) | auto |
| `--output-dir` | Folder to write into | `output/` |
| `-f, --format` | `json` or `csv` | `json` |
| `-p, --max-pages` | Max pages to crawl | `50` |
| `-d, --max-depth` | Max link depth from the seed | `3` |
| `--delay` | Seconds between requests | `0.5` |
| `--timeout` | Per-request timeout (seconds) | `10` |
| `--user-agent` | User-Agent header | package default |
| `--ignore-robots` | Ignore `robots.txt` | off |
| `--allow-external` | Follow links to other domains | off |
| `-v, --verbose` | Verbose logging | off |

## Output schema

Each page is an object with: `url`, `status_code`, `title`, `description`,
`text`, `links`, `depth`, `content_type`, and `error`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Note

Scrape responsibly: respect site terms of service and `robots.txt`, and keep
request rates reasonable.
