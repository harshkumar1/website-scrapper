# website-scrapper

A polite, configurable website scraper. Crawls a site starting from a seed
URL, extracts each page's visible text and links, and writes the results to
CSV and JSON. Supports **incremental crawling** — re-running the same command
picks up where a previous run left off and only adds or updates pages whose
content has changed.

## Features

- Breadth-first crawl with configurable page and depth limits
- Stays within the seed domain by default (opt out with `--allow-external`)
- Honors `robots.txt` (opt out with `--ignore-robots`)
- Polite rate limiting between requests (`--delay`)
- Incremental output — each run appends to existing CSV/JSON and skips unchanged pages
- Metadata JSON tracks content hashes so re-crawls detect changes efficiently
- Resolves relative links to absolute URLs and de-duplicates them

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Every run produces three files inside the output folder (`output/` by default):

| File | Purpose |
|------|---------|
| `<name>.csv` | Main data — one row per page with all columns |
| `<name>.json` | Same data in JSON format |
| `<name>_metadata.json` | Lightweight index used to detect changes between runs |

When `-o` is omitted, the base name is derived from the domain
(e.g. `output/example.com.csv`).

```bash
# First run — scrapes up to 50 pages
website-scrapper https://example.com -o results

# Second run — resumes from where the first left off, skips unchanged pages
website-scrapper https://example.com -o results

website-scrapper https://example.com -o results -p 200
```

You can also run it as a module: `python -m scraper https://example.com`.

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Base output name (extensions added automatically) | auto from domain |
| `--output-dir` | Folder to write into | `output/` |
| `-p, --max-pages` | Max pages to crawl per run | `50` |
| `-d, --max-depth` | Max link depth from the seed | `3` |
| `--delay` | Seconds between requests | `0.5` |
| `--timeout` | Per-request timeout (seconds) | `10` |
| `--user-agent` | User-Agent header | package default |
| `--ignore-robots` | Ignore `robots.txt` | off |
| `--allow-external` | Follow links to other domains | off |
| `-v, --verbose` | Verbose logging | off |

## Output schema

### CSV / JSON columns

| Column | Description |
|--------|-------------|
| `doc_id` | UUID for the page |
| `base_url` | Root URL of the website |
| `canonical_url` | Actual URL fetched (after redirects) |
| `crawl_dt` | Timestamp when the page was crawled |
| `doc_last_modified_dt` | `Last-Modified` header value, or crawl time if absent |
| `content_type` | `Content-Type` header |
| `content_source_type` | Always `web` |
| `scheme_type` | URL scheme, e.g. `HTTPS` |
| `scheme_name` | Domain name |
| `lang` | Language from `Content-Language` header, default `en` |
| `doc_version` | Incremented each time content changes across runs |
| `is_active` | `true` for successful HTML pages |
| `status` | HTTP status code |
| `crawl_depth` | Link depth from the seed URL |
| `normalized_url` | URL with fragments stripped, trailing slashes removed, lowercased |
| `content` | Visible page text (CSV/JSON only, not in metadata) |

### Metadata JSON

The metadata file contains one entry per URL with: `doc_id`, `base_url`,
`canonical_url`, `crawl_dt`, `doc_last_modified_dt`, `content_hash`, and
`doc_version`. The `content_hash` (SHA-256) is compared on re-runs to
determine whether a page needs updating.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Note

Scrape responsibly: respect site terms of service and `robots.txt`, and keep
request rates reasonable.
