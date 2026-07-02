"""Data ingestion pipeline: load merc.csv, clean, normalize, and populate training_data.

Idempotent: truncate + reload, so re-running doesn't duplicate rows.
Emits a summary: rows in, rows dropped (by reason), rows written, RM price range.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from sqlalchemy.orm import Session

from app.db import get_engine, get_session
from app.orm import Base, TrainingData


# Import canonical model mapping and numeric-only list.
from ml.constants import CANONICAL_MODELS, NUMERIC_ONLY_MODELS, normalize_model


class IngestSummary(TypedDict):
    """Summary of an ingest run."""

    timestamp: str
    rows_in: int
    rows_dropped_numeric_only: int
    rows_dropped_sanity_filter: int
    rows_written: int
    price_rm_min: int
    price_rm_max: int


def load_merc_csv(csv_path: Path | str) -> list[dict]:
    """Load merc.csv and return list of dicts (raw, unprocessed).

    Args:
        csv_path: Path to merc.csv.

    Returns:
        List of dicts with keys: model, year, price, transmission, mileage,
        fuelType, tax, mpg, engineSize.

    Raises:
        FileNotFoundError: If csv_path does not exist.
        csv.Error: If CSV is malformed.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"merc.csv not found at {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return rows


def clean_and_normalize(
    raw_rows: list[dict],
    fx_gbp_to_rm: float,
    current_year: int,
) -> tuple[list[dict], IngestSummary]:
    """Clean, validate, and normalize raw merc.csv rows.

    Cleaning rules:
    1. Strip and normalize model to canonical label.
    2. Drop numeric-only models (230/220/200/180) with logged count.
    3. Sanity filters: 1970 ≤ year ≤ current_year, price > 0, mileage ≥ 0, engineSize ≥ 0.
    4. Compute age = current_year - year; price_rm = round(price_gbp * fx_gbp_to_rm).

    Args:
        raw_rows: List of dicts from load_merc_csv.
        fx_gbp_to_rm: FX rate (GBP to RM) from config.
        current_year: Current year for age calculation (usually datetime.now().year).

    Returns:
        Tuple of:
        - cleaned_rows: list of cleaned, ready-to-insert dicts.
        - summary: IngestSummary with counts and stats.
    """
    cleaned = []
    dropped_numeric_only = 0
    dropped_sanity_filter = 0
    price_rm_values = []

    for raw_row in raw_rows:
        # Normalize model.
        raw_model = raw_row.get("model", "").strip()
        canonical_model = normalize_model(raw_model)

        # Check for numeric-only (drop).
        if canonical_model is None and raw_model in NUMERIC_ONLY_MODELS:
            dropped_numeric_only += 1
            continue

        # Check for unrecognized model.
        if canonical_model is None:
            dropped_sanity_filter += 1
            continue

        # Parse numeric fields.
        try:
            year = int(raw_row.get("year", 0))
            price_gbp = float(raw_row.get("price", 0))
            mileage = int(raw_row.get("mileage", 0))
            engine_size = float(raw_row.get("engineSize", 0))
            tax = float(raw_row.get("tax", 0))
            mpg = float(raw_row.get("mpg", 0))
        except (ValueError, TypeError):
            dropped_sanity_filter += 1
            continue

        # Sanity filters.
        if not (1970 <= year <= current_year):
            dropped_sanity_filter += 1
            continue
        if price_gbp <= 0:
            dropped_sanity_filter += 1
            continue
        if mileage < 0:
            dropped_sanity_filter += 1
            continue
        if engine_size < 0:
            dropped_sanity_filter += 1
            continue

        # Compute derived fields.
        age = current_year - year
        price_rm = round(price_gbp * fx_gbp_to_rm)

        # Build cleaned row.
        transmission = raw_row.get("transmission", "unknown").strip()
        fuel_type = raw_row.get("fuelType", "unknown").strip()

        cleaned_row = {
            "model": canonical_model,
            "year": year,
            "age": age,
            "price_rm": price_rm,
            "transmission": transmission,
            "mileage": mileage,
            "fuel_type": fuel_type,
            "tax": tax,
            "mpg": mpg,
            "engine_size": engine_size,
        }
        cleaned.append(cleaned_row)
        price_rm_values.append(price_rm)

    # Build summary.
    summary: IngestSummary = {
        "timestamp": datetime.utcnow().isoformat(),
        "rows_in": len(raw_rows),
        "rows_dropped_numeric_only": dropped_numeric_only,
        "rows_dropped_sanity_filter": dropped_sanity_filter,
        "rows_written": len(cleaned),
        "price_rm_min": min(price_rm_values) if price_rm_values else 0,
        "price_rm_max": max(price_rm_values) if price_rm_values else 0,
    }

    return cleaned, summary


def ingest_to_db(
    cleaned_rows: list[dict],
    session: Session,
) -> None:
    """Idempotently load cleaned rows into training_data table.

    Truncates the table, then inserts. Safe to re-run.

    Args:
        cleaned_rows: List of cleaned dicts from clean_and_normalize.
        session: SQLAlchemy session.
    """
    # Truncate.
    session.query(TrainingData).delete()
    session.commit()

    # Insert.
    for row in cleaned_rows:
        training_row = TrainingData(
            model=row["model"],
            year=row["year"],
            age=row["age"],
            price_rm=row["price_rm"],
            transmission=row["transmission"],
            mileage=row["mileage"],
            fuel_type=row["fuel_type"],
            tax=row["tax"],
            mpg=row["mpg"],
            engine_size=row["engine_size"],
            source="merc.csv",
        )
        session.add(training_row)

    session.commit()


def main(
    csv_path: Path | str = "data/merc.csv",
    fx_gbp_to_rm: float = 5.90,
    current_year: int | None = None,
) -> IngestSummary:
    """Main entry point for ingest pipeline.

    Loads merc.csv, cleans, normalizes, and populates training_data.

    Args:
        csv_path: Path to merc.csv (default: data/merc.csv from repo root).
        fx_gbp_to_rm: FX rate GBP->RM (default: 5.90, overrideable for tuning).
        current_year: Year for age calculation (default: now).

    Returns:
        IngestSummary with run statistics.

    Raises:
        FileNotFoundError: If merc.csv not found.
    """
    if current_year is None:
        current_year = datetime.utcnow().year

    print(f"[ingest] Loading merc.csv from {csv_path}...")
    raw_rows = load_merc_csv(csv_path)
    print(f"[ingest] Loaded {len(raw_rows)} rows.")

    print(f"[ingest] Cleaning and normalizing (FX: {fx_gbp_to_rm} GBP->RM)...")
    cleaned_rows, summary = clean_and_normalize(raw_rows, fx_gbp_to_rm, current_year)

    print("[ingest] Populating training_data (truncate + reload)...")
    session = get_session()
    try:
        ingest_to_db(cleaned_rows, session)
    finally:
        session.close()

    # Print summary.
    print("\n" + "=" * 60)
    print("INGEST SUMMARY")
    print("=" * 60)
    print(f"Timestamp:              {summary['timestamp']}")
    print(f"Rows in (merc.csv):     {summary['rows_in']}")
    print(f"Rows dropped (numeric): {summary['rows_dropped_numeric_only']}")
    print(f"Rows dropped (sanity):  {summary['rows_dropped_sanity_filter']}")
    print(f"Rows written:           {summary['rows_written']}")
    print(f"Price RM range:         {summary['price_rm_min']:,} – {summary['price_rm_max']:,}")
    print("=" * 60 + "\n")

    return summary


if __name__ == "__main__":
    # This can be called as: python -m ml.ingest
    # Or integrated into a larger pipeline.
    main()
