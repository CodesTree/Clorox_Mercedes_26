"""Read-only join projection for marketplace rows plus approved vehicle specs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote

from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.orm import MarketListing, VehicleSpec

JOINED_SPECS_COLUMNS = [
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
    "source listing_url",
    "specs source_url",
    "match_confidence",
]

MatchConfidence = Literal["exact", "partial", "unmatched"]
JoinedSpecsRow = dict[str, Any]


def _specific_listing_model(listing: MarketListing) -> str:
    return f"{listing.model} {listing.variant}" if listing.variant else listing.model


def _variant_key(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\bC\s?200\b", value, re.I)
    if match:
        return "C200"
    return re.sub(r"[^A-Z0-9]+", "", value.upper()) or None


def _year_in_spec_range(year: int, spec: VehicleSpec) -> bool | None:
    if spec.year_start is None or spec.year_end is None:
        return None
    return spec.year_start <= year <= spec.year_end


def match_vehicle_spec(
    listing: MarketListing,
    specs: list[VehicleSpec],
) -> tuple[VehicleSpec | None, MatchConfidence]:
    listing_variant = _variant_key(listing.variant)
    if not listing_variant:
        return None, "unmatched"

    candidates = [
        spec
        for spec in specs
        if spec.model == listing.model and _variant_key(spec.variant) == listing_variant
    ]
    exact = [spec for spec in candidates if _year_in_spec_range(listing.year, spec) is True]
    if exact:
        return exact[0], "exact"
    partial = [spec for spec in candidates if _year_in_spec_range(listing.year, spec) is None]
    if partial:
        return partial[0], "partial"
    return None, "unmatched"


def joined_specs_row(
    listing: MarketListing,
    spec: VehicleSpec | None,
    confidence: MatchConfidence,
) -> JoinedSpecsRow:
    return {
        "specific model of the car": spec.specific_model if spec else _specific_listing_model(listing),
        "engine type": spec.engine_type if spec else None,
        "engine cc": spec.engine_cc if spec else None,
        "engine aspiration": spec.engine_aspiration if spec else None,
        "gear type/transmission": spec.transmission if spec else None,
        "number of gears": spec.number_of_gears if spec else None,
        "top speed (km/h)": spec.top_speed_kmh if spec else None,
        "front brakes": spec.front_brakes if spec else None,
        "rear brakes": spec.rear_brakes if spec else None,
        "front suspension": spec.front_suspension if spec else None,
        "rear suspension": spec.rear_suspension if spec else None,
        "boot space (litres)": spec.boot_space_litres if spec else None,
        "seat capacity": spec.seat_capacity if spec else None,
        "number of doors": spec.number_of_doors if spec else None,
        "torque (Nm)": spec.torque_nm if spec else None,
        "time for 0-100 km/h (s)": spec.zero_to_100_kmh_s if spec else None,
        "mileage": listing.mileage,
        "fuel type": spec.fuel_type if spec else None,
        "year of the car": listing.year,
        "price (RM)": listing.price_rm,
        "source listing_url": listing.listing_url,
        "specs source_url": spec.source_url if spec else None,
        "match_confidence": confidence,
    }


def load_joined_specs_rows(session: Session) -> list[JoinedSpecsRow]:
    listings = (
        session.query(MarketListing)
        .order_by(MarketListing.source.asc(), MarketListing.scraped_at.desc(), MarketListing.id.asc())
        .all()
    )
    specs = session.query(VehicleSpec).order_by(VehicleSpec.id.asc()).all()
    specs.sort(
        key=lambda spec: (
            "/fixture/" in spec.source_url,
            unquote(spec.source_url),
            "%" in spec.source_url,
            spec.source_url,
        )
    )
    rows: list[JoinedSpecsRow] = []
    for listing in listings:
        spec, confidence = match_vehicle_spec(listing, specs)
        rows.append(joined_specs_row(listing, spec, confidence))
    return rows


def write_joined_specs_csv(rows: list[JoinedSpecsRow], output_path: Path | str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOINED_SPECS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export market listings joined to approved vehicle specs")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, int]:
    args = parse_args(argv)
    init_db()
    session = SessionLocal()
    try:
        rows = load_joined_specs_rows(session)
    finally:
        session.close()
    write_joined_specs_csv(rows, args.output)

    summary = {
        "rows": len(rows),
        "exact": sum(row["match_confidence"] == "exact" for row in rows),
        "partial": sum(row["match_confidence"] == "partial" for row in rows),
        "unmatched": sum(row["match_confidence"] == "unmatched" for row in rows),
    }
    print("\n" + "=" * 60)
    print("MARKET + VEHICLE SPECS EXPORT SUMMARY")
    print("=" * 60)
    print(f"Rows:      {summary['rows']}")
    print(f"Exact:     {summary['exact']}")
    print(f"Partial:   {summary['partial']}")
    print(f"Unmatched: {summary['unmatched']}")
    print(f"Output:    {args.output}")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    main()
