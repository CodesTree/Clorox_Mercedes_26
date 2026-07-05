"""Project scraped market listings into a training-like feature shape.

This is a Phase 01 -> Phase 02 handoff helper. It does not merge scraped rows
into training_data; it provides comparable feature rows for market comps,
calibration, and analysis.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import TypedDict

from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.orm import MarketListing
from ml.ingest import CURRENT_YEAR


MARKET_FEATURE_COLUMNS = [
    "source",
    "listing_url",
    "model",
    "year",
    "age",
    "mileage",
    "price_rm",
    "transmission",
    "fuel_type",
    "engine_size",
    "variant",
    "location",
    "seller_type",
    "posted_at",
    "scraped_at",
]


class MarketFeatureRow(TypedDict):
    source: str
    listing_url: str
    model: str
    year: int
    age: int
    mileage: int | None
    price_rm: int
    transmission: str | None
    fuel_type: str | None
    engine_size: float | None
    variant: str | None
    location: str | None
    seller_type: str
    posted_at: str | None
    scraped_at: str


def market_listing_to_feature_row(
    listing: MarketListing,
    *,
    current_year: int = CURRENT_YEAR,
) -> MarketFeatureRow:
    """Convert one market listing to the feature shape Phase 02 can compare.

    engine_size is intentionally left nullable: Phase 01 only uses values that
    were parsed from the market listing, and the current listing schema has no
    verified engine-size field.
    """
    return {
        "source": listing.source,
        "listing_url": listing.listing_url,
        "model": listing.model,
        "year": listing.year,
        "age": current_year - listing.year,
        "mileage": listing.mileage,
        "price_rm": listing.price_rm,
        "transmission": listing.transmission,
        "fuel_type": listing.fuel_type,
        "engine_size": None,
        "variant": listing.variant,
        "location": listing.location,
        "seller_type": listing.seller_type,
        "posted_at": listing.posted_at,
        "scraped_at": listing.scraped_at.isoformat()
        if hasattr(listing.scraped_at, "isoformat")
        else str(listing.scraped_at),
    }


def load_market_feature_rows(
    session: Session,
    *,
    current_year: int = CURRENT_YEAR,
) -> list[MarketFeatureRow]:
    """Read market_listings and return training-like feature rows."""
    listings = (
        session.query(MarketListing)
        .order_by(MarketListing.source.asc(), MarketListing.scraped_at.desc(), MarketListing.id.asc())
        .all()
    )
    return [
        market_listing_to_feature_row(listing, current_year=current_year)
        for listing in listings
    ]


def write_market_features_csv(rows: list[MarketFeatureRow], output_path: Path | str) -> None:
    """Write projected market rows to a CSV file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MARKET_FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_rows(rows: list[MarketFeatureRow]) -> dict:
    """Return a compact summary for CLI output/tests."""
    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    return {
        "rows": len(rows),
        "by_source": by_source,
        "missing_engine_size": sum(row["engine_size"] is None for row in rows),
        "missing_transmission": sum(row["transmission"] is None for row in rows),
        "missing_fuel_type": sum(row["fuel_type"] is None for row in rows),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export market_listings as Phase 02 comparable feature rows"
    )
    parser.add_argument("--output", type=Path, help="Optional CSV output path")
    parser.add_argument("--current-year", type=int, default=CURRENT_YEAR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    init_db()
    session = SessionLocal()
    try:
        rows = load_market_feature_rows(session, current_year=args.current_year)
    finally:
        session.close()

    if args.output:
        write_market_features_csv(rows, args.output)

    summary = summarize_rows(rows)
    print("\n" + "=" * 60)
    print("MARKET FEATURE EXPORT SUMMARY")
    print("=" * 60)
    print(f"Rows:                 {summary['rows']}")
    print(f"By source:            {summary['by_source']}")
    print(f"Missing engine_size:  {summary['missing_engine_size']}")
    print(f"Missing transmission: {summary['missing_transmission']}")
    print(f"Missing fuel_type:    {summary['missing_fuel_type']}")
    if args.output:
        print(f"Output:               {args.output}")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    main()
