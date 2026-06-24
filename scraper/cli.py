"""Command-line interface for the website scraper."""

from __future__ import annotations

import argparse
import logging
import sys
from urllib.parse import urlparse

from . import __version__, output
from .crawler import Crawler


def _default_basename(url: str) -> str:
    """Build a base filename from the domain."""
    return urlparse(url).netloc.replace(":", "_") or "site"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="website-scrapper",
        description="Crawl a website and extract page content.",
    )
    parser.add_argument("url", help="Seed URL to start crawling from")
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Base output name (without extension). CSV, JSON, and metadata "
        "files are derived from this. Bare names go inside the output dir.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=output.DEFAULT_OUTPUT_DIR,
        help=f"Directory to write output into (default: {output.DEFAULT_OUTPUT_DIR}/)",
    )
    parser.add_argument(
        "-p", "--max-pages", type=int, default=50, help="Max pages to crawl (default: 50)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between requests (default: 0.5)",
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds"
    )
    parser.add_argument(
        "--user-agent",
        default=f"website-scrapper/{__version__} (+https://github.com/)",
        help="User-Agent header to send",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Do not honor robots.txt (use responsibly)",
    )
    parser.add_argument(
        "--allow-external",
        action="store_true",
        help="Follow links to other domains",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    basename = args.output or _default_basename(args.url)

    csv_path = output.resolve_path(basename, "csv", args.output_dir)
    json_path = output.resolve_path(basename, "json", args.output_dir)
    meta_path = output.resolve_path(f"{basename}_metadata", "json", args.output_dir)

    existing_meta = output.load_metadata(meta_path)
    already_visited = set(existing_meta.keys())

    frontier: list[tuple[str, int]] = []
    if already_visited:
        for entry in existing_meta.values():
            parent_depth = int(entry.get("crawl_depth", 0))
            for link in entry.get("links", []):
                if link not in already_visited:
                    frontier.append((link, parent_depth + 1))
        logging.info(
            "Resuming crawl — %d URLs already scraped, %d new URLs in frontier",
            len(already_visited),
            len(frontier),
        )

    try:
        crawler = Crawler(
            args.url,
            max_pages=args.max_pages,
            max_depth=999,
            delay=args.delay,
            timeout=args.timeout,
            user_agent=args.user_agent,
            respect_robots=not args.ignore_robots,
            same_domain_only=not args.allow_external,
            already_visited=already_visited,
            frontier=frontier,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    pages = crawler.crawl()

    new, updated, skipped = output.write_incremental(pages, csv_path, json_path, meta_path)

    logging.info(
        "Done. Crawled %d page(s): %d new, %d updated, %d skipped (unchanged). "
        "Files: %s, %s, %s",
        len(pages), new, updated, skipped, csv_path, json_path, meta_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
