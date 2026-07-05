from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi.testclient import TestClient

from app import orm
from app.db import SessionLocal, init_db
from app.main import app
from app.routers import market, valuation
from app.schemas import DepreciationOut, DepreciationPoint, PredictOut


PROFILE_PAYLOAD = {
    "model": "SL CLASS",
    "year": 2016,
    "mileage": 42000,
    "transmission": "Automatic",
    "fuel_type": "Petrol",
    "engine_size": 5.5,
    "original_purchase_price_rm": 738000,
    "mpg": 30.4,
    "tax": 305.0,
    "service_history_count": 6,
    "service_history_total": 7,
}


class StubPredictor:
    def predict(self, profile):
        assert profile.model == "SL CLASS"
        return PredictOut(value_rm=738000, low_rm=712000, high_rm=765000, confidence=0.92)

    def depreciation(self, profile, years: int):
        return DepreciationOut(
            points=[
                DepreciationPoint(year=2026, value_rm=738000, retained_pct=1.0),
                DepreciationPoint(year=2027, value_rm=701100, retained_pct=0.95),
                DepreciationPoint(year=2028, value_rm=666045, retained_pct=0.9025),
            ][: years + 1]
        )


def clear_market_listings(model: str) -> None:
    init_db()
    with SessionLocal() as session:
        session.query(orm.MarketListing).filter(orm.MarketListing.model == model).delete()
        session.commit()


def test_predict_with_stub_predictor_returns_band(monkeypatch):
    monkeypatch.setattr(valuation, "predictor_service", StubPredictor())
    with TestClient(app) as client:
        resp = client.post("/predict", json=PROFILE_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json() == {
        "value_rm": 738000,
        "low_rm": 712000,
        "high_rm": 765000,
        "confidence": 0.92,
        "currency": "RM",
    }


def test_predict_without_model_artifact_returns_actionable_503():
    with TestClient(app) as client:
        resp = client.post("/predict", json=PROFILE_PAYLOAD)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "train model first: python -m ml.train"}


def test_depreciation_with_stub_predictor_returns_points(monkeypatch):
    monkeypatch.setattr(valuation, "predictor_service", StubPredictor())
    with TestClient(app) as client:
        resp = client.get("/depreciation", params={"profile_id": 1, "years": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert [p["year"] for p in body["points"]] == [2026, 2027, 2028]
    assert body["points"][0]["retained_pct"] == 1.0


def test_depreciation_with_original_purchase_price_does_not_need_model_artifact():
    with TestClient(app) as client:
        resp = client.get("/depreciation", params={"profile_id": 1, "years": 2})
    assert resp.status_code == 200
    body = resp.json()
    current_year = datetime.now().year
    current_age = current_year - PROFILE_PAYLOAD["year"]
    expected_value = int(
        (Decimal(PROFILE_PAYLOAD["original_purchase_price_rm"]) * (Decimal("0.95") ** current_age))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    assert body["points"][0] == {
        "year": current_year,
        "value_rm": expected_value,
        "retained_pct": round(expected_value / PROFILE_PAYLOAD["original_purchase_price_rm"], 4),
    }


def test_vehicle_profile_is_seeded_and_updatable():
    with TestClient(app) as client:
        seeded = client.get("/vehicle/profile", params={"id": 1})
        updated = client.put(
            "/vehicle/profile",
            json={**PROFILE_PAYLOAD, "mileage": 45000, "service_history_count": 7},
        )
        reread = client.get("/vehicle/profile", params={"id": 1})

    assert seeded.status_code == 200
    assert seeded.json()["model"] == "SL CLASS"
    assert seeded.json()["workshop"]
    assert updated.status_code == 200
    assert updated.json()["mileage"] == 45000
    assert updated.json()["service_history_count"] == 7
    assert reread.json()["mileage"] == 45000


def test_market_comps_empty_db_returns_nulls():
    clear_market_listings("E CLASS")
    with TestClient(app) as client:
        resp = client.get("/market/comps", params={"model": "E CLASS", "year": 2020})
    assert resp.status_code == 200
    assert resp.json() == {"comps": [], "median_rm": None, "delta_pct": None, "n": 0}


def test_market_comps_matches_year_window_and_computes_median():
    clear_market_listings("C CLASS")
    with SessionLocal() as session:
        session.add_all(
            [
                orm.MarketListing(
                    source="mudah",
                    listing_url="https://example.test/c1",
                    model="C CLASS",
                    variant="C200",
                    year=2018,
                    price_rm=200000,
                    mileage=45000,
                    transmission="Automatic",
                    fuel_type="Petrol",
                    location="Kuala Lumpur",
                    seller_type="dealer",
                    posted_at="2026-07-01",
                ),
                orm.MarketListing(
                    source="carlist",
                    listing_url="https://example.test/c2",
                    model="C CLASS",
                    variant="C300",
                    year=2019,
                    price_rm=220000,
                    mileage=38000,
                    transmission="Automatic",
                    fuel_type="Petrol",
                    location="Selangor",
                    seller_type="dealer",
                    posted_at="2026-07-01",
                ),
                orm.MarketListing(
                    source="mudah",
                    listing_url="https://example.test/c3",
                    model="C CLASS",
                    variant="C180",
                    year=2011,
                    price_rm=90000,
                    mileage=120000,
                    transmission="Automatic",
                    fuel_type="Petrol",
                    location="Johor",
                    seller_type="private",
                    posted_at="2026-07-01",
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        resp = client.get("/market/comps", params={"model": "C CLASS", "year": 2018, "limit": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert body["n"] == 2
    assert body["median_rm"] == 210000
    assert body["delta_pct"] is None
    assert {comp["listing_url"] for comp in body["comps"]} == {
        "https://example.test/c1",
        "https://example.test/c2",
    }


def test_market_comps_computes_delta_when_predictor_is_available(monkeypatch):
    class MarketStubPredictor:
        def predict(self, profile):
            assert profile.model == "SL CLASS"
            return PredictOut(value_rm=770000, low_rm=700000, high_rm=800000, confidence=0.92)

    clear_market_listings("SL CLASS")
    with SessionLocal() as session:
        session.add_all(
            [
                orm.MarketListing(
                    source="mudah",
                    listing_url="https://example.test/sl1",
                    model="SL CLASS",
                    variant="SL400",
                    year=2016,
                    price_rm=700000,
                    mileage=42000,
                    transmission="Automatic",
                    fuel_type="Petrol",
                    location="Kuala Lumpur",
                    seller_type="dealer",
                    posted_at="2026-07-01",
                ),
                orm.MarketListing(
                    source="carlist",
                    listing_url="https://example.test/sl2",
                    model="SL CLASS",
                    variant="SL500",
                    year=2017,
                    price_rm=700000,
                    mileage=39000,
                    transmission="Automatic",
                    fuel_type="Petrol",
                    location="Selangor",
                    seller_type="dealer",
                    posted_at="2026-07-01",
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(market, "predictor_service", MarketStubPredictor())
    with TestClient(app) as client:
        resp = client.get("/market/comps", params={"model": "SL CLASS", "year": 2016})

    assert resp.status_code == 200
    body = resp.json()
    assert body["median_rm"] == 700000
    assert body["delta_pct"] == 0.1


def test_obd_snapshot_is_simulated_and_in_declared_ranges():
    with TestClient(app) as client:
        resp = client.get("/obd/snapshot", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert 700 <= body["rpm"] <= 3600
    assert 70.0 <= body["coolant_c"] <= 105.0
    assert 12.4 <= body["battery_v"] <= 14.4
    assert 0 <= body["health"] <= 100
    assert body["odo_km"] >= 0
    assert body["simulated"] is True
    datetime.fromisoformat(body["ts"])


def test_obd_stream_returns_sse_snapshots():
    with TestClient(app) as client:
        with client.stream("GET", "/obd/stream", params={"profile_id": 1, "max_events": 2}) as resp:
            body = resp.read().decode("utf-8")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert body.count("event: snapshot") == 2
    assert '"simulated":true' in body


def test_odx_faults_parse_sample_or_degrade_to_empty_list():
    with TestClient(app) as client:
        resp = client.get("/odx/faults", params={"profile_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["faults"]) >= 1
    assert {"code", "description", "severity", "system"} <= set(body["faults"][0])


def test_booking_persists_and_returns_dry_run_payload_without_keys():
    booking = {
        "profile_id": 1,
        "name": "Chan",
        "workshop": "Hap Seng Star KL",
        "car_model": "SL CLASS",
        "purpose": "Certified inspection",
        "date": "2026-07-10",
        "time": "10:00",
    }
    with TestClient(app) as client:
        resp = client.post("/booking", json=booking)

    assert resp.status_code == 200
    body = resp.json()
    assert body["booking_id"] > 0
    assert body["status"] == "dry_run"
    assert body["dispatched"] is False
    assert body["dry_run"] is True
    # /booking dispatches via Telegram (see tests/05_agents_tests/test_booking_route.py);
    # with no Telegram credentials configured it falls back to dry-run without a payload.
    assert body["payload"] is None

    with SessionLocal() as session:
        row = session.get(orm.Booking, body["booking_id"])
        assert row is not None
        assert row.status == "dry_run"
