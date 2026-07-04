"""Market listing feature projection tests."""

import csv
from datetime import datetime

from app.db import SessionLocal, init_db
from app.orm import MarketListing
from ml.market_features import (
    MARKET_FEATURE_COLUMNS,
    load_market_feature_rows,
    market_listing_to_feature_row,
    summarize_rows,
    write_market_features_csv,
)


def _listing(**overrides) -> MarketListing:
    values = {
        "source": "mudah",
        "listing_url": "https://www.mudah.my/example-1.htm",
        "model": "C_CLASS",
        "variant": "C200",
        "year": 2020,
        "price_rm": 99800,
        "mileage": 87500,
        "transmission": "Automatic",
        "fuel_type": "Petrol",
        "location": "Selangor",
        "seller_type": "dealer",
        "posted_at": "2026-07-03",
        "scraped_at": datetime(2026, 7, 3, 12, 0, 0),
    }
    values.update(overrides)
    return MarketListing(**values)


def test_market_listing_to_feature_row_preserves_fields_and_leaves_engine_size_null():
    row = market_listing_to_feature_row(_listing(), current_year=2026)

    assert row["source"] == "mudah"
    assert row["listing_url"] == "https://www.mudah.my/example-1.htm"
    assert row["model"] == "C_CLASS"
    assert row["year"] == 2020
    assert row["age"] == 6
    assert row["mileage"] == 87500
    assert row["price_rm"] == 99800
    assert row["transmission"] == "Automatic"
    assert row["fuel_type"] == "Petrol"
    assert row["engine_size"] is None


def test_load_market_feature_rows_from_db():
    init_db()
    session = SessionLocal()
    try:
        session.add(_listing())
        session.add(
            _listing(
                source="carlist",
                listing_url="https://www.carlist.my/example-2",
                transmission=None,
                fuel_type=None,
            )
        )
        session.commit()

        rows = load_market_feature_rows(session, current_year=2026)
    finally:
        session.close()

    assert len(rows) == 2
    assert {row["source"] for row in rows} == {"mudah", "carlist"}
    assert summarize_rows(rows) == {
        "rows": 2,
        "by_source": {"carlist": 1, "mudah": 1},
        "missing_engine_size": 2,
        "missing_transmission": 1,
        "missing_fuel_type": 1,
    }


def test_write_market_features_csv(tmp_path):
    output = tmp_path / "market_features.csv"
    row = market_listing_to_feature_row(_listing(), current_year=2026)

    write_market_features_csv([row], output)

    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert reader.fieldnames == MARKET_FEATURE_COLUMNS
    assert rows[0]["model"] == "C_CLASS"
    assert rows[0]["age"] == "6"
    assert rows[0]["engine_size"] == ""
