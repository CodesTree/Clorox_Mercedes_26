from pathlib import Path

from sqlalchemy import create_engine, inspect

from app import orm

EXPECTED_TABLES = {
    "training_data",
    "market_listings",
    "vehicle_specs",
    "vehicle_profiles",
    "bookings",
    "dtc_codes",
}


def test_all_five_tables_create_on_temp_sqlite(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'orm.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_listing_url_is_unique(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'uniq.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("market_listings")}
    assert "listing_url" in cols
    uniques = [u["column_names"] for u in inspect(engine).get_unique_constraints("market_listings")]
    indexes = [i["column_names"] for i in inspect(engine).get_indexes("market_listings") if i["unique"]]
    assert ["listing_url"] in uniques + indexes


def test_vehicle_specs_source_url_is_unique(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'specs.db').as_posix()}")
    orm.Base.metadata.create_all(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("vehicle_specs")}
    assert {
        "source_url",
        "specific_model",
        "engine_cc",
        "torque_nm",
        "zero_to_100_kmh_s",
    }.issubset(cols)
    uniques = [u["column_names"] for u in inspect(engine).get_unique_constraints("vehicle_specs")]
    indexes = [i["column_names"] for i in inspect(engine).get_indexes("vehicle_specs") if i["unique"]]
    assert ["source_url"] in uniques + indexes
