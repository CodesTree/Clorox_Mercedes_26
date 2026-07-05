from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from app.schemas import DepreciationOut, DepreciationPoint, PredictOut

MODEL_UNAVAILABLE_DETAIL = "train model first: python -m ml.train"
DEFAULT_ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "model.joblib"
DEFAULT_DEPRECIATION_RATE = Decimal("0.05")


class ModelUnavailable(RuntimeError):
    def __init__(self, detail: str = MODEL_UNAVAILABLE_DETAIL):
        super().__init__(detail)
        self.detail = detail


def _field(profile: Any, name: str, default: Any = None) -> Any:
    if isinstance(profile, dict):
        return profile.get(name, default)
    return getattr(profile, name, default)


def _feature_row(profile: Any) -> dict[str, Any]:
    year = int(_field(profile, "year"))
    return {
        "model": _field(profile, "model"),
        "year": year,
        "age": max(0, datetime.now().year - year),
        "mileage": _field(profile, "mileage"),
        "transmission": _field(profile, "transmission"),
        "fuel_type": _field(profile, "fuel_type"),
        "engine_size": _field(profile, "engine_size"),
        "mpg": _field(profile, "mpg"),
        "tax": _field(profile, "tax"),
    }


class PredictorService:
    def __init__(self, artifact_path: Path = DEFAULT_ARTIFACT_PATH):
        self.artifact_path = artifact_path
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.artifact_path.exists():
            raise ModelUnavailable()
        try:
            import joblib  # type: ignore
        except ImportError as exc:
            raise ModelUnavailable("install joblib/scikit-learn and train model first: python -m ml.train") from exc
        self._model = joblib.load(self.artifact_path)
        return self._model

    def predict(self, profile: Any) -> PredictOut:
        model = self._load_model()

        if hasattr(model, "predict_profile"):
            result = model.predict_profile(profile)
        elif callable(model) and not hasattr(model, "predict"):
            result = model(_feature_row(profile))
        else:
            result = model.predict([_feature_row(profile)])

        if isinstance(result, dict):
            return PredictOut(**result)

        value = int(round(float(result[0] if isinstance(result, (list, tuple)) else result)))
        low = max(0, int(round(value * 0.92)))
        high = max(low, int(round(value * 1.08)))
        return PredictOut(value_rm=value, low_rm=low, high_rm=high, confidence=0.92)

    def depreciation(self, profile: Any, years: int) -> DepreciationOut:
        original_price = _field(profile, "original_purchase_price_rm")
        if original_price is None:
            original_price = self.predict(profile).value_rm

        original_price_dec = Decimal(int(original_price))
        current_year = datetime.now().year
        vehicle_age = max(0, current_year - int(_field(profile, "year", current_year)))
        annual_retention = Decimal("1") - DEFAULT_DEPRECIATION_RATE
        points = []
        for offset in range(years + 1):
            years_since_purchase = vehicle_age + offset
            value_dec = original_price_dec * (annual_retention**years_since_purchase)
            value = max(0, int(value_dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
            retained = round(value / int(original_price), 4) if int(original_price) > 0 else 0.0
            points.append(
                DepreciationPoint(
                    year=current_year + offset,
                    value_rm=value,
                    retained_pct=retained,
                )
            )
        return DepreciationOut(points=points)
