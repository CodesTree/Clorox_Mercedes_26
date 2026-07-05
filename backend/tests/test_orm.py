from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text

from app import db
from app import orm

EXPECTED_TABLES = {
    "training_data",
    "market_listings",
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


def test_init_db_adds_original_purchase_price_column_to_existing_sqlite_profile_table(
    tmp_path: Path,
    monkeypatch,
):
    db_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE vehicle_profiles (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    model VARCHAR NOT NULL,
                    year INTEGER NOT NULL,
                    mileage INTEGER NOT NULL,
                    transmission VARCHAR NOT NULL,
                    fuel_type VARCHAR NOT NULL,
                    engine_size FLOAT NOT NULL,
                    service_history_count INTEGER NOT NULL,
                    service_history_total INTEGER NOT NULL,
                    service_history_max INTEGER NOT NULL,
                    workshop VARCHAR,
                    glb_asset VARCHAR,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )

    monkeypatch.setattr(db, "_settings", SimpleNamespace(database_url=f"sqlite:///{db_path.as_posix()}"))
    monkeypatch.setattr(db, "engine", engine)

    db.init_db()

    cols = {c["name"] for c in inspect(engine).get_columns("vehicle_profiles")}
    assert "original_purchase_price_rm" in cols
