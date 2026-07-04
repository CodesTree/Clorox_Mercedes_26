"""Read-only joined market/spec export tests."""

import csv
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import orm
from app.orm import MarketListing, TrainingData, VehicleSpec
from scraper.export_joined_specs import (
    JOINED_SPECS_COLUMNS,
    load_joined_specs_rows,
    match_vehicle_spec,
    write_joined_specs_csv,
)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'joined.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _listing(**overrides) -> MarketListing:
    values = {
        "source": "carlist",
        "listing_url": "https://www.carlist.my/example-c200",
        "model": "C_CLASS",
        "variant": "C200",
        "year": 2023,
        "price_rm": 228000,
        "mileage": 12000,
        "transmission": "Automatic",
        "fuel_type": "Petrol",
        "location": "Kuala Lumpur",
        "seller_type": "dealer",
        "posted_at": "2026-07-03",
        "scraped_at": datetime(2026, 7, 3, 12, 0, 0),
    }
    values.update(overrides)
    return MarketListing(**values)


def _spec(**overrides) -> VehicleSpec:
    values = {
        "source": "ultimatespecs",
        "source_url": "https://www.ultimatespecs.com/fixture/mercedes-c200",
        "make": "Mercedes-Benz",
        "model": "C_CLASS",
        "variant": "C200",
        "generation": "W206",
        "year_start": 2021,
        "year_end": 2024,
        "specific_model": "Mercedes Benz W206 Class C 200 2021 2024 Specs",
        "engine_type": "Inline 4",
        "engine_cc": 1496,
        "engine_aspiration": "Turbo",
        "transmission": "9 speed Automatic",
        "number_of_gears": 9,
        "top_speed_kmh": 246,
        "front_brakes": "Vented Discs",
        "rear_brakes": "Discs",
        "front_suspension": "Independent McPherson",
        "rear_suspension": "Independent multi-link",
        "boot_space_litres": 455,
        "seat_capacity": 5,
        "number_of_doors": 4,
        "torque_nm": 300,
        "zero_to_100_kmh_s": 7.3,
        "fuel_type": "Petrol",
        "scraped_at": datetime(2026, 7, 4, 12, 0, 0),
    }
    values.update(overrides)
    return VehicleSpec(**values)


def _training_row() -> TrainingData:
    return TrainingData(
        model="C_CLASS",
        year=2023,
        age=3,
        price_rm=228000,
        transmission="Automatic",
        mileage=12000,
        fuel_type="Petrol",
        tax=150.0,
        mpg=40.0,
        engine_size=1.5,
    )


def test_match_vehicle_spec_uses_model_variant_and_year_for_exact_match():
    spec, confidence = match_vehicle_spec(_listing(), [_spec()])

    assert spec is not None
    assert spec.source_url == "https://www.ultimatespecs.com/fixture/mercedes-c200"
    assert confidence == "exact"


def test_match_vehicle_spec_leaves_non_variant_match_unmatched():
    spec, confidence = match_vehicle_spec(_listing(variant="C300"), [_spec()])

    assert spec is None
    assert confidence == "unmatched"


def test_joined_specs_export_column_order_and_blank_unmatched_specs(tmp_path):
    output = tmp_path / "market_specs_joined_export.csv"
    session = _session(tmp_path)
    try:
        session.add(_listing(variant="C300"))
        session.commit()
        rows = load_joined_specs_rows(session)
    finally:
        session.close()

    write_joined_specs_csv(rows, output)

    with output.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        exported = list(reader)

    assert reader.fieldnames == JOINED_SPECS_COLUMNS
    assert exported[0]["match_confidence"] == "unmatched"
    assert exported[0]["source listing_url"] == "https://www.carlist.my/example-c200"
    assert exported[0]["specs source_url"] == ""
    assert exported[0]["engine cc"] == ""
    assert exported[0]["price (RM)"] == "228000"
    assert exported[0]["mileage"] == "12000"


def test_joined_specs_export_reads_without_writing_training_data(tmp_path):
    session = _session(tmp_path)
    try:
        session.add(_training_row())
        session.add(_listing())
        session.add(_spec())
        session.commit()
        before_training_count = session.query(TrainingData).count()

        rows = load_joined_specs_rows(session)

        after_training_count = session.query(TrainingData).count()
        assert not session.new
        assert not session.dirty
        assert not session.deleted
    finally:
        session.close()

    assert len(rows) == 1
    assert rows[0]["match_confidence"] == "exact"
    assert rows[0]["engine cc"] == 1496
    assert rows[0]["source listing_url"] == "https://www.carlist.my/example-c200"
    assert rows[0]["specs source_url"] == "https://www.ultimatespecs.com/fixture/mercedes-c200"
    assert after_training_count == before_training_count
