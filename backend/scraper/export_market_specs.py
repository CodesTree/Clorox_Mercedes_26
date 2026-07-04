"""Read-only CSV projection of scraped marketplace listings for Phase 02.

This exporter only uses fields already stored in market_listings. Engineering
spec fields stay blank unless an approved source is added to the schema later.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.orm import MarketListing


MARKET_SPECS_COLUMNS = [
    "specific model of the car",
    "engine type",
    "engine cc",
    "engine aspiration",
    "gear type/transmission",
    "number of gears",
    "top speed (km/h)",
    "front brakes",
    "rear brakes",
    "front suspension",
    "rear suspension",
    "boot space (litres)",
    "seat capacity",
    "number of doors",
    "torque (Nm)",
    "time for 0-100 km/h (s)",
    "mileage",
    "fuel type",
    "year of the car",
    "price (RM)",
]

COMPACT_MARKET_SPECS_COLUMNS = [
    "source",
    "listing_url",
    "specific model of the car",
    "gear type/transmission",
    "mileage",
    "fuel type",
    "year of the car",
    "price (RM)",
    "variant",
    "location",
    "seller_type",
    "posted_at",
    "scraped_at",
]

TECHNICAL_SPEC_COLUMNS = [
    "engine type",
    "engine cc",
    "engine aspiration",
    "number of gears",
    "top speed (km/h)",
    "front brakes",
    "rear brakes",
    "front suspension",
    "rear suspension",
    "boot space (litres)",
    "seat capacity",
    "number of doors",
    "torque (Nm)",
    "time for 0-100 km/h (s)",
]

MarketSpecsRow = dict[str, Any]


def _specific_model(listing: MarketListing) -> str:
    if listing.variant:
        return f"{listing.model} {listing.variant}"
    return listing.model


def market_listing_to_specs_row(listing: MarketListing) -> MarketSpecsRow:
    """Project one listing into the requested Phase 02 column contract."""
    row: MarketSpecsRow = {column: None for column in MARKET_SPECS_COLUMNS}
    row.update(
        {
            "specific model of the car": _specific_model(listing),
            "gear type/transmission": listing.transmission,
            "mileage": listing.mileage,
            "fuel type": listing.fuel_type,
            "year of the car": listing.year,
            "price (RM)": listing.price_rm,
        }
    )
    return row


def market_listing_to_compact_specs_row(listing: MarketListing) -> MarketSpecsRow:
    """Project one listing into a human-friendly marketplace review shape."""
    return {
        "source": listing.source,
        "listing_url": listing.listing_url,
        "specific model of the car": _specific_model(listing),
        "gear type/transmission": listing.transmission,
        "mileage": listing.mileage,
        "fuel type": listing.fuel_type,
        "year of the car": listing.year,
        "price (RM)": listing.price_rm,
        "variant": listing.variant,
        "location": listing.location,
        "seller_type": listing.seller_type,
        "posted_at": listing.posted_at,
        "scraped_at": listing.scraped_at.isoformat()
        if hasattr(listing.scraped_at, "isoformat")
        else str(listing.scraped_at),
    }


def _query_market_listings(session: Session) -> list[MarketListing]:
    return (
        session.query(MarketListing)
        .order_by(MarketListing.source.asc(), MarketListing.scraped_at.desc(), MarketListing.id.asc())
        .all()
    )


def load_market_specs_rows(session: Session) -> list[MarketSpecsRow]:
    """Read market_listings without mutating listing or training tables."""
    return [market_listing_to_specs_row(listing) for listing in _query_market_listings(session)]


def load_compact_market_specs_rows(session: Session) -> list[MarketSpecsRow]:
    """Read market_listings into the compact human-review shape."""
    return [
        market_listing_to_compact_specs_row(listing)
        for listing in _query_market_listings(session)
    ]


def write_market_specs_csv(
    rows: list[MarketSpecsRow],
    output_path: Path | str,
    *,
    columns: list[str] = MARKET_SPECS_COLUMNS,
) -> None:
    """Write the read-only projection to CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarize_rows(rows: list[MarketSpecsRow]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "missing_technical_specs": sum(
            all(row.get(column) is None for column in TECHNICAL_SPEC_COLUMNS) for row in rows
        ),
        "missing_transmission": sum(row.get("gear type/transmission") is None for row in rows),
        "missing_fuel_type": sum(row.get("fuel type") is None for row in rows),
        "missing_mileage": sum(row.get("mileage") is None for row in rows),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export market_listings into the requested Phase 02 specs CSV shape"
    )
    parser.add_argument("--output", type=Path, required=True, help="CSV output path")
    parser.add_argument(
        "--format",
        choices=("full", "compact"),
        default="full",
        help="CSV schema: full preserves requested spec columns; compact is easier to review",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, int]:
    args = parse_args(argv)
    init_db()
    session = SessionLocal()
    try:
        if args.format == "compact":
            rows = load_compact_market_specs_rows(session)
            columns = COMPACT_MARKET_SPECS_COLUMNS
        else:
            rows = load_market_specs_rows(session)
            columns = MARKET_SPECS_COLUMNS
    finally:
        session.close()

    write_market_specs_csv(rows, args.output, columns=columns)
    summary = summarize_rows(rows)

    print("\n" + "=" * 60)
    print("MARKET LISTING SPECS EXPORT SUMMARY")
    print("=" * 60)
    print(f"Format:                  {args.format}")
    print(f"Rows:                    {summary['rows']}")
    print(f"Missing technical specs: {summary['missing_technical_specs']}")
    print(f"Missing transmission:    {summary['missing_transmission']}")
    print(f"Missing fuel type:       {summary['missing_fuel_type']}")
    print(f"Missing mileage:         {summary['missing_mileage']}")
    print(f"Output:                  {args.output}")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    main()
