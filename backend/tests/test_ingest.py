"""Phase 01 ingest tests."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.orm import TrainingData
from ml.constants import normalize_model
from ml.ingest import clean_and_normalize, ingest_to_db, load_merc_csv, main

REPO_ROOT = Path(__file__).resolve().parents[2]
MERC_CSV = REPO_ROOT / "data" / "sample_odx" / "merc.csv"


@pytest.fixture
def db_session() -> Session:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_canonical_model_mapping():
    assert normalize_model(" SLK") == "SLK_CLASS"
    assert normalize_model("SL CLASS") == "SL_CLASS"
    assert normalize_model("C Class") == "C_CLASS"
    assert normalize_model("GL Class") == "GL_CLASS"
    assert normalize_model("CLS Class") == "CLS_CLASS"


def test_numeric_only_rows_dropped():
    raw = [
        {"model": "230", "year": 2007, "price": 4500, "mileage": 94000, "engineSize": 0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 29.4},
        {"model": "C Class", "year": 2017, "price": 10000, "mileage": 10000, "engineSize": 2.0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 40.0},
    ]
    cleaned, summary = clean_and_normalize(raw, fx_gbp_to_rm=5.90, current_year=2026)
    assert summary["rows_dropped_numeric_only"] == 1
    assert len(cleaned) == 1
    assert cleaned[0]["model"] == "C_CLASS"


def test_gbp_to_rm_math():
    raw = [
        {"model": "C Class", "year": 2017, "price": 10000, "mileage": 10000, "engineSize": 2.0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 40.0},
    ]
    cleaned, _ = clean_and_normalize(raw, fx_gbp_to_rm=5.90, current_year=2026)
    assert cleaned[0]["price_rm"] == 59000
    assert cleaned[0]["age"] == 9


def test_sanity_filters_drop_invalid_rows():
    raw = [
        {"model": "C Class", "year": 1969, "price": 10000, "mileage": 0, "engineSize": 2.0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 40.0},
        {"model": "C Class", "year": 2017, "price": 0, "mileage": 0, "engineSize": 2.0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 40.0},
        {"model": "Unknown", "year": 2017, "price": 10000, "mileage": 0, "engineSize": 2.0, "transmission": "Automatic", "fuelType": "Petrol", "tax": 0, "mpg": 40.0},
    ]
    cleaned, summary = clean_and_normalize(raw, fx_gbp_to_rm=5.90, current_year=2026)
    assert len(cleaned) == 0
    assert summary["rows_dropped_sanity_filter"] == 3


def test_idempotent_reload(db_session: Session):
    raw = load_merc_csv(MERC_CSV)
    cleaned, _ = clean_and_normalize(raw, fx_gbp_to_rm=5.90, current_year=2026)

    ingest_to_db(cleaned, db_session)
    first_count = db_session.query(TrainingData).count()

    ingest_to_db(cleaned, db_session)
    second_count = db_session.query(TrainingData).count()

    assert first_count == second_count == len(cleaned)


def test_main_uses_full_corpus(monkeypatch):
    monkeypatch.setenv("FX_GBP_TO_RM", "5.90")
    summary = main(csv_path=MERC_CSV, fx_gbp_to_rm=5.90, current_year=2026)
    assert summary["rows_in"] > 10000
    assert summary["rows_dropped_numeric_only"] == 4
    assert summary["rows_written"] > 0
    assert summary["price_rm_min"] > 0
