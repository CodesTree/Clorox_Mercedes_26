import pytest

from ml import train
from ml.predict import Predictor
from tests.test_ml_train import _engineered_frame


@pytest.fixture(scope="module")
def predictor(tmp_path_factory):
    artifacts = tmp_path_factory.mktemp("artifacts")
    train.main(df=_engineered_frame(), artifacts_dir=artifacts, n_splits=3, n_estimators=40)
    return Predictor(model_path=artifacts / "model.joblib")


def _profile(**over):
    base = {
        "model_class": "C Class", "year": 2018, "age": 8, "mileage": 60_000,
        "transmission": "Automatic", "fuel_type": "Petrol", "engine_size": 2.0,
        "source_market": "uk",
    }
    base.update(over)
    return base


def test_predict_returns_ordered_positive_bounds(predictor):
    out = predictor.predict(_profile())
    assert out["low_rm"] <= out["value_rm"] <= out["high_rm"]
    assert out["low_rm"] > 0
    assert 0.0 <= out["confidence"] <= 1.0


def test_depreciation_is_monotonically_non_increasing(predictor):
    points = predictor.depreciation(_profile(), years=5)
    values = [p["value_rm"] for p in points]
    assert values == sorted(values, reverse=True)
    assert all(p["value_rm"] >= 0 for p in points)
    assert points[0]["retained_pct"] == pytest.approx(1.0, abs=1e-6)


def test_unknown_category_does_not_crash(predictor):
    out = predictor.predict(_profile(model_class="ZZ Unknown", fuel_type="Electric"))
    assert out["value_rm"] > 0
