"""Scraper orchestrator: fetch → extract → normalise → upsert."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict

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


class PipelineSummary(TypedDict):
    timestamp: str
    mudah_fetched: int
    mudah_stored: int
    mudah_skipped: int
    carlist_fetched: int
    carlist_stored: int
    carlist_skipped: int
    total_stored: int


@dataclass
class PipelineConfig:
    max_listings_per_run: int = SCRAPER_DEFAULTS["max_listings_per_run"]
    use_fixtures: bool = False
    use_network: bool = True


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

    mudah_html = _load_html(
        "mudah", fetcher=fetcher, search_url=MUDAH_SEARCH_URL, use_fixtures=config.use_fixtures
    )
    carlist_html = _load_html(
        "carlist", fetcher=fetcher, search_url=CARLIST_SEARCH_URL, use_fixtures=config.use_fixtures
    )

    mudah_rows, mudah_stats = mudah.extract_search_results(mudah_html)
    carlist_rows, carlist_stats = carlist.extract_search_results(carlist_html)

    cap = config.max_listings_per_run
    combined = (mudah_rows + carlist_rows)[:cap]
    stored = upsert_listings(session, combined)

    summary: PipelineSummary = {
        "timestamp": datetime.utcnow().isoformat(),
        "mudah_fetched": mudah_stats["fetched"],
        "mudah_stored": min(len(mudah_rows), cap),
        "mudah_skipped": mudah_stats["skipped_non_mercedes"] + mudah_stats["skipped_unparseable"],
        "carlist_fetched": carlist_stats["fetched"],
        "carlist_stored": min(len(carlist_rows), max(0, cap - len(mudah_rows))),
        "carlist_skipped": carlist_stats["skipped_non_mercedes"]
        + carlist_stats["skipped_unparseable"],
        "total_stored": stored,
    }
    return summary


def main(use_fixtures: bool = False, use_network: bool = True) -> PipelineSummary:
    """CLI entry: python -m scraper.pipeline"""
    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=use_fixtures, use_network=use_network),
        )
    finally:
        session.close()

    print("\n" + "=" * 60)
    print("SCRAPER PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Timestamp:        {summary['timestamp']}")
    print(f"Mudah fetched:    {summary['mudah_fetched']}")
    print(f"Mudah stored:     {summary['mudah_stored']} (skipped {summary['mudah_skipped']})")
    print(f"Carlist fetched:  {summary['carlist_fetched']}")
    print(f"Carlist stored:   {summary['carlist_stored']} (skipped {summary['carlist_skipped']})")
    print(f"Total stored:     {summary['total_stored']}")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    main(use_fixtures=True, use_network=False)
