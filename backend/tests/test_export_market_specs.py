"""Read-only market_listings specs export tests."""

import csv
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import orm
from app.orm import MarketListing, TrainingData
from scraper.export_market_specs import (
    COMPACT_MARKET_SPECS_COLUMNS,
    MARKET_SPECS_COLUMNS,
    TECHNICAL_SPEC_COLUMNS,
    load_compact_market_specs_rows,
    load_market_specs_rows,
    market_listing_to_compact_specs_row,
    market_listing_to_specs_row,
    write_market_specs_csv,
)


def _listing(**overrides) -> MarketListing:
    values = {
        "source": "mudah",
        "listing_url": "https://www.mudah.my/example-1.htm",
        "model": "C_CLASS",
        "variant": "C200 AMG Line",
        "year": 2020,
        "price_rm": 149000,
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


def _training_row(**overrides) -> TrainingData:
    values = {
        "model": "C_CLASS",
        "year": 2020,
        "age": 6,
        "price_rm": 149000,
        "transmission": "Automatic",
        "mileage": 87500,
        "fuel_type": "Petrol",
        "tax": 150.0,
        "mpg": 40.0,
        "engine_size": 1.5,
    }
    values.update(overrides)
    return TrainingData(**values)


def test_market_specs_projection_has_requested_columns_and_populates_listing_fields():
    row = market_listing_to_specs_row(_listing())

    assert list(row.keys()) == MARKET_SPECS_COLUMNS
    assert len(MARKET_SPECS_COLUMNS) == 20
    assert row["specific model of the car"] == "C_CLASS C200 AMG Line"
    assert row["gear type/transmission"] == "Automatic"
    assert row["mileage"] == 87500
    assert row["fuel type"] == "Petrol"
    assert row["year of the car"] == 2020
    assert row["price (RM)"] == 149000


def test_market_specs_projection_leaves_unavailable_technical_specs_blank():
    row = market_listing_to_specs_row(_listing())

    assert all(row[column] is None for column in TECHNICAL_SPEC_COLUMNS)


def test_market_specs_csv_writes_blank_cells_for_unavailable_technical_specs(tmp_path):
    output = tmp_path / "market_listings_specs_export.csv"
    rows = [market_listing_to_specs_row(_listing(transmission=None, fuel_type=None))]

    write_market_specs_csv(rows, output)

    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        exported = list(reader)

    assert reader.fieldnames == MARKET_SPECS_COLUMNS
    assert exported[0]["specific model of the car"] == "C_CLASS C200 AMG Line"
    assert exported[0]["gear type/transmission"] == ""
    assert exported[0]["fuel type"] == ""
    assert all(exported[0][column] == "" for column in TECHNICAL_SPEC_COLUMNS)


def test_compact_market_specs_projection_excludes_unavailable_engineering_specs():
    row = market_listing_to_compact_specs_row(_listing())

    assert list(row.keys()) == COMPACT_MARKET_SPECS_COLUMNS
    assert all(column not in row for column in TECHNICAL_SPEC_COLUMNS)
    assert "engine cc" not in row
    assert "torque (Nm)" not in row


def test_compact_market_specs_csv_includes_traceability_fields(tmp_path):
    output = tmp_path / "market_listings_specs_export_compact.csv"
    rows = [market_listing_to_compact_specs_row(_listing())]

    write_market_specs_csv(rows, output, columns=COMPACT_MARKET_SPECS_COLUMNS)

    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        exported = list(reader)

    assert reader.fieldnames == COMPACT_MARKET_SPECS_COLUMNS
    assert exported[0]["source"] == "mudah"
    assert exported[0]["listing_url"] == "https://www.mudah.my/example-1.htm"
    assert exported[0]["specific model of the car"] == "C_CLASS C200 AMG Line"
    assert all(column not in exported[0] for column in TECHNICAL_SPEC_COLUMNS)


def test_market_specs_export_reads_market_listings_without_writing_training_data(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'export.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        session.add(_training_row())
        session.add(_listing())
        session.commit()
        before_training_count = session.query(TrainingData).count()

        rows = load_market_specs_rows(session)
        compact_rows = load_compact_market_specs_rows(session)

        after_training_count = session.query(TrainingData).count()
        assert not session.new
        assert not session.dirty
        assert not session.deleted
    finally:
        session.close()

    assert len(rows) == 1
    assert len(compact_rows) == 1
    assert rows[0]["specific model of the car"] == "C_CLASS C200 AMG Line"
    assert compact_rows[0]["listing_url"] == "https://www.mudah.my/example-1.htm"
    assert after_training_count == before_training_count
