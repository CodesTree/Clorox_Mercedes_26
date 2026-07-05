from app.schemas import VehicleProfileIn
from app.schemas import PredictOut
from app.services.market import compute_delta_pct
from app.services.obd_sim import HealthInputs, compute_health_score
from app.services.odx_service import OdxFaultService
from app.services.predictor import PredictorService


class _FixedPredictor(PredictorService):
    def predict(self, profile):
        return PredictOut(value_rm=999999, low_rm=900000, high_rm=1000000, confidence=0.92)


def test_market_delta_pct_uses_predicted_minus_median_over_median():
    assert compute_delta_pct(predict_value_rm=252000, median_rm=210000) == 0.2


def test_depreciation_uses_original_purchase_price_compounded_by_vehicle_age():
    from datetime import datetime
    from types import SimpleNamespace

    current_year = datetime.now().year
    profile = SimpleNamespace(year=current_year - 2, original_purchase_price_rm=100000)

    out = _FixedPredictor().depreciation(profile, years=2)

    assert [point.value_rm for point in out.points] == [90250, 85738, 81451]
    assert [point.retained_pct for point in out.points] == [0.9025, 0.8574, 0.8145]


def test_health_score_penalizes_faults_missed_service_and_bad_battery():
    excellent = compute_health_score(
        HealthInputs(
            mileage=42000,
            service_history_count=7,
            service_history_total=7,
            fault_count=0,
            coolant_c=88.0,
            battery_v=13.7,
        )
    )
    poor = compute_health_score(
        HealthInputs(
            mileage=180000,
            service_history_count=2,
            service_history_total=7,
            fault_count=3,
            coolant_c=104.0,
            battery_v=12.4,
        )
    )
    assert excellent > poor
    assert 0 <= poor <= 100


def test_odx_service_missing_sample_dir_returns_empty_list(tmp_path):
    service = OdxFaultService(sample_dir=tmp_path / "missing")
    assert service.list_faults() == []


def test_obd_simulator_can_use_vehicle_profile_fields():
    from app.services.obd_sim import ObdSimulator

    profile = VehicleProfileIn(
        model="SL CLASS",
        year=2016,
        mileage=42000,
        transmission="Automatic",
        fuel_type="Petrol",
        engine_size=5.5,
        service_history_count=6,
        service_history_total=7,
    )
    snap = ObdSimulator(seed=42).snapshot(profile=profile, fault_count=1)
    assert snap.simulated is True
    assert snap.odo_km == 42000
