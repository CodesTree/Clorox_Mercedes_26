from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app import schemas


def test_health_out():
    h = schemas.HealthOut(status="ok", version="0.1.0")
    assert h.status == "ok"


def test_vehicle_profile_in_minimal():
    p = schemas.VehicleProfileIn(
        model="SL CLASS", year=2016, mileage=42000, transmission="Automatic",
        fuel_type="Petrol", engine_size=5.5,
    )
    assert p.mpg is None and p.tax is None


def test_vehicle_profile_in_rejects_negative_mileage():
    with pytest.raises(ValidationError):
        schemas.VehicleProfileIn(
            model="SL CLASS", year=2016, mileage=-1, transmission="Automatic",
            fuel_type="Petrol", engine_size=5.5,
        )


def test_predict_out_currency_is_fixed_to_rm():
    out = schemas.PredictOut(value_rm=738000, low_rm=712000, high_rm=765000, confidence=0.92)
    assert out.currency == "RM"


def test_market_comps_out_allows_empty_market():
    out = schemas.MarketCompsOut(comps=[], median_rm=None, delta_pct=None, n=0)
    assert out.comps == []


def test_market_listing_source_is_constrained():
    with pytest.raises(ValidationError):
        schemas.MarketListingOut(
            source="ebay", listing_url="https://x.test/1", model="C Class",
            year=2018, price_rm=180000,
        )


def test_obd_snapshot_is_always_labelled_simulated():
    snap = schemas.ObdSnapshotOut(
        rpm=831, coolant_c=77.0, battery_v=12.6, health=87, odo_km=42000,
        ts=datetime.now(timezone.utc),
    )
    assert snap.simulated is True
    with pytest.raises(ValidationError):
        schemas.ObdSnapshotOut(
            rpm=831, coolant_c=77.0, battery_v=12.6, health=87, odo_km=42000,
            ts=datetime.now(timezone.utc), simulated=False,
        )


def test_depreciation_out():
    out = schemas.DepreciationOut(
        points=[schemas.DepreciationPoint(year=2026, value_rm=738000, retained_pct=1.0)]
    )
    assert out.points[0].retained_pct == 1.0


def test_faults_out():
    out = schemas.FaultsOut(
        faults=[schemas.FaultOut(code="P0301", description="d", severity="warn", system="engine")]
    )
    assert out.faults[0].code == "P0301"


def test_advisory_interpret_out():
    out = schemas.AdvisoryInterpretOut(
        recommendation="Repair and keep",
        summary="Repair and keep is recommended.",
        horizon_years=5,
        current_value_rm=738000,
        horizon_value_rm=640000,
        depreciation_loss_rm=98000,
        total_repair_cost_rm=18400,
        repairs=[schemas.RepairItemOut(name="Brake wear service", cost_rm=7800)],
    )
    assert out.llm_used is False
    assert out.repairs[0].cost_rm == 7800


def test_booking_roundtrip():
    b_in = schemas.BookingIn(
        profile_id=1, name="Chan", workshop="Hap Seng Star KL", car_model="SL CLASS",
        purpose="Certified inspection", date="2026-07-10", time="10:00",
    )
    b_out = schemas.BookingOut(booking_id=1, status="dry_run", dispatched=False, dry_run=True)
    assert b_in.workshop == "Hap Seng Star KL" and b_out.dry_run is True
