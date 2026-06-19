"""Command-line interface for the website scraper."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from urllib.parse import urlparse

from . import __version__, output
from .crawler import Crawler


def _default_filename(url: str, fmt: str) -> str:
    """Build a filename from the domain and current timestamp."""
    host = urlparse(url).netloc.replace(":", "_") or "site"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{host}_{stamp}.{fmt}"


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
        help="Output filename (default: auto from domain+timestamp). "
        "Bare names go inside the output dir; paths are kept as-is.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=output.DEFAULT_OUTPUT_DIR,
        help=f"Directory to write output into (default: {output.DEFAULT_OUTPUT_DIR}/)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "-p", "--max-pages", type=int, default=50, help="Max pages to crawl (default: 50)"
    )
    parser.add_argument(
        "-d", "--max-depth", type=int, default=3, help="Max link depth (default: 3)"
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

    try:
        crawler = Crawler(
            args.url,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            delay=args.delay,
            timeout=args.timeout,
            user_agent=args.user_agent,
            respect_robots=not args.ignore_robots,
            same_domain_only=not args.allow_external,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    pages = crawler.crawl()

    filename = args.output or _default_filename(args.url, args.format)
    path = output.resolve_path(filename, args.format, args.output_dir)
    output.write(pages, args.format, path)

    logging.info("Done. Scraped %d page(s) -> %s", len(pages), path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
