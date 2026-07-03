"""Scraper orchestrator: fetch → extract → normalise → upsert."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, TypedDict

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.orm import MarketListing
from ml.constants import SCRAPER_DEFAULTS
from scraper.base import PoliteFetcher, ScraperConfig
from scraper.carlist import SEARCH_URL as CARLIST_SEARCH_URL
from scraper.carlist import CarlistExtractor
from scraper.mudah import SEARCH_URL as MUDAH_SEARCH_URL
from scraper.mudah import MudahExtractor

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SiteStatus = Literal["ok", "blocked_by_robots", "fetch_failed", "extract_failed"]
ScraperSite = Literal["mudah", "carlist", "all"]


class PipelineSummary(TypedDict):
    timestamp: str
    mudah_status: SiteStatus
    mudah_fetched: int
    mudah_stored: int
    mudah_skipped: int
    mudah_error: str
    carlist_status: SiteStatus
    carlist_fetched: int
    carlist_stored: int
    carlist_skipped: int
    carlist_error: str
    total_stored: int


class SiteResult(TypedDict):
    status: SiteStatus
    error: str
    rows: list[dict]
    fetched: int
    skipped: int


@dataclass
class PipelineConfig:
    # TODO(P01): Live marketplace extraction remains deferred because approved Gate 1 URLs are blocked
    # by robots.txt; keep fixture coverage and explicit live smoke reporting until an approved data
    # source/path is available.
    max_listings_per_run: int = SCRAPER_DEFAULTS["max_listings_per_run"]
    use_fixtures: bool = False
    use_network: bool = True
    site: ScraperSite = "all"


def _build_fetcher() -> PoliteFetcher:
    settings = get_settings()
    return PoliteFetcher(
        ScraperConfig(
            user_agent=settings.scraper_user_agent,
            rate_limit_seconds=settings.scraper_rate_limit_seconds,
            rate_limit_jitter=0.5,
            cache_dir=Path(__file__).parent / "cache",
            cache_ttl_hours=24,
        )
    )


def _load_html(
    source: str,
    *,
    fetcher: PoliteFetcher | None,
    search_url: str,
    use_fixtures: bool,
) -> str:
    fixture_map = {
        "mudah": FIXTURES_DIR / "mudah_search_results.html",
        "carlist": FIXTURES_DIR / "carlist_search_results.html",
    }
    fixture_path = fixture_map[source]
    if use_fixtures:
        if not fixture_path.exists():
            raise FileNotFoundError(f"Missing fixture: {fixture_path}")
        return fixture_path.read_text(encoding="utf-8")
    if fetcher is None:
        raise RuntimeError(f"No fetcher available for live {source} scrape")
    return fetcher.fetch(search_url)


def _empty_site_result(status: SiteStatus, error: str) -> SiteResult:
    return SiteResult(status=status, error=error, rows=[], fetched=0, skipped=0)


def _run_site(
    source: str,
    *,
    fetcher: PoliteFetcher | None,
    search_url: str,
    use_fixtures: bool,
    extract: Callable[[str], tuple[list[dict], dict]],
) -> SiteResult:
    try:
        html = _load_html(
            source,
            fetcher=fetcher,
            search_url=search_url,
            use_fixtures=use_fixtures,
        )
    except ValueError as exc:
        message = str(exc)
        status: SiteStatus = "blocked_by_robots" if "robots.txt disallows" in message else "fetch_failed"
        logger.warning("%s scrape skipped: %s", source, message)
        return _empty_site_result(status, message)
    except Exception as exc:
        message = str(exc)
        logger.warning("%s fetch failed: %s", source, message)
        return _empty_site_result("fetch_failed", message)

    if not html:
        return _empty_site_result("fetch_failed", "empty response")

    try:
        rows, stats = extract(html)
    except Exception as exc:
        message = str(exc)
        logger.warning("%s extraction failed: %s", source, message)
        return _empty_site_result("extract_failed", message)

    skipped = stats["skipped_non_mercedes"] + stats["skipped_unparseable"]
    return SiteResult(
        status="ok",
        error="",
        rows=rows,
        fetched=stats["fetched"],
        skipped=skipped,
    )


def upsert_listings(session: Session, rows: list[dict]) -> int:
    """Upsert listings by unique listing_url. Returns count written/updated."""
    written = 0
    for row in rows:
        existing = (
            session.query(MarketListing)
            .filter(MarketListing.listing_url == row["listing_url"])
            .one_or_none()
        )
        if existing:
            for field in (
                "model",
                "variant",
                "year",
                "price_rm",
                "mileage",
                "transmission",
                "fuel_type",
                "location",
                "seller_type",
                "posted_at",
            ):
                setattr(existing, field, row.get(field))
            existing.scraped_at = row["scraped_at"]
        else:
            session.add(
                MarketListing(
                    source=row["source"],
                    listing_url=row["listing_url"],
                    model=row["model"],
                    variant=row.get("variant"),
                    year=row["year"],
                    price_rm=row["price_rm"],
                    mileage=row.get("mileage"),
                    transmission=row.get("transmission"),
                    fuel_type=row.get("fuel_type"),
                    location=row.get("location"),
                    seller_type=row.get("seller_type", "unknown"),
                    posted_at=row.get("posted_at"),
                    scraped_at=row["scraped_at"],
                )
            )
        written += 1
    session.commit()
    return written


def run_pipeline(
    session: Session,
    *,
    config: PipelineConfig | None = None,
    fetcher: PoliteFetcher | None = None,
) -> PipelineSummary:
    """Execute the full scrape pipeline."""
    config = config or PipelineConfig()
    fetcher = None if config.use_fixtures or not config.use_network else (fetcher or _build_fetcher())

    mudah = MudahExtractor()
    carlist = CarlistExtractor()

    mudah_result = (
        _run_site(
            "mudah",
            fetcher=fetcher,
            search_url=MUDAH_SEARCH_URL,
            use_fixtures=config.use_fixtures,
            extract=mudah.extract_search_results,
        )
        if config.site in {"mudah", "all"}
        else _empty_site_result("ok", "")
    )
    carlist_result = (
        _run_site(
            "carlist",
            fetcher=fetcher,
            search_url=CARLIST_SEARCH_URL,
            use_fixtures=config.use_fixtures,
            extract=carlist.extract_search_results,
        )
        if config.site in {"carlist", "all"}
        else _empty_site_result("ok", "")
    )

    cap = config.max_listings_per_run
    mudah_rows = mudah_result["rows"][:cap]
    remaining = max(0, cap - len(mudah_rows))
    carlist_rows = carlist_result["rows"][:remaining]
    combined = mudah_rows + carlist_rows
    stored = upsert_listings(session, combined)

    summary: PipelineSummary = {
        "timestamp": datetime.utcnow().isoformat(),
        "mudah_status": mudah_result["status"],
        "mudah_fetched": mudah_result["fetched"],
        "mudah_stored": len(mudah_rows),
        "mudah_skipped": mudah_result["skipped"],
        "mudah_error": mudah_result["error"],
        "carlist_status": carlist_result["status"],
        "carlist_fetched": carlist_result["fetched"],
        "carlist_stored": len(carlist_rows),
        "carlist_skipped": carlist_result["skipped"],
        "carlist_error": carlist_result["error"],
        "total_stored": stored,
    }
    return summary


def _print_site_summary(summary: PipelineSummary, source: Literal["mudah", "carlist"]) -> None:
    label = "Mudah" if source == "mudah" else "Carlist"
    print(f"{label} status:     {summary[f'{source}_status']}")
    print(f"{label} fetched:    {summary[f'{source}_fetched']}")
    print(
        f"{label} stored:     {summary[f'{source}_stored']} "
        f"(skipped {summary[f'{source}_skipped']})"
    )
    if summary[f"{source}_error"]:
        print(f"{label} error:      {summary[f'{source}_error']}")


def print_summary(
    summary: PipelineSummary,
    *,
    mode: str,
    site: ScraperSite,
    use_network: bool,
    use_fixtures: bool,
) -> None:
    print("\n" + "=" * 60)
    print("SCRAPER PIPELINE SUMMARY")
    print("=" * 60)
    print(f"mode={mode}")
    print(f"site={site}")
    print(f"use_network={use_network}")
    print(f"use_fixtures={use_fixtures}")
    print(f"Timestamp:        {summary['timestamp']}")
    if site in {"mudah", "all"}:
        _print_site_summary(summary, "mudah")
    if site in {"carlist", "all"}:
        _print_site_summary(summary, "carlist")
    print(f"Total stored:     {summary['total_stored']}")
    print("=" * 60 + "\n")


def main(
    use_fixtures: bool = False,
    use_network: bool = True,
    site: ScraperSite = "all",
) -> PipelineSummary:
    """Run the scraper pipeline programmatically."""
    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=use_fixtures, use_network=use_network, site=site),
        )
    finally:
        session.close()

    mode = "fixtures" if use_fixtures else "live"
    print_summary(
        summary,
        mode=mode,
        site=site,
        use_network=use_network,
        use_fixtures=use_fixtures,
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 01 scraper pipeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Fetch live pages with robots.txt enforcement")
    mode.add_argument("--fixtures", action="store_true", help="Use saved fixture HTML with no network")
    parser.add_argument(
        "--site",
        choices=("mudah", "carlist", "all"),
        default="all",
        help="Site to run",
    )
    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> PipelineSummary:
    args = parse_args(argv)
    use_fixtures = bool(args.fixtures)
    use_network = bool(args.live)
    return main(use_fixtures=use_fixtures, use_network=use_network, site=args.site)


if __name__ == "__main__":
    cli()
